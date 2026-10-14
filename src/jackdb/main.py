import json
import tempfile
import os
from io import TextIOWrapper
from json import JSONDecodeError


class JackDB:
    """An embedded key-value database backed by a JSON Lines append-only log.

    Every mutation (``put``/``del``) is recorded in memory and appended to the
    log file when :meth:`flush_logs` is called. On open, the log is replayed in
    order (later records win) to rebuild the in-memory dictionary; a torn final
    line from a crash mid-write is discarded, so the database always opens to a
    consistent prefix of the log.
    """

    def __init__(self, replay_path: str = ""):
        """Open (or create) the log file and replay it into memory.

        :param replay_path: Path to the JSON Lines log file. Required.
        :raises ValueError: If ``replay_path`` is empty.
        """
        self.replay_file: TextIOWrapper
        self.data_dict = {}
        self.replay_path = replay_path
        self.records = []
        self.log_length = 0

        if self.replay_path == "":
            raise ValueError("replay_path is required")
        self.replay_file = open(self.replay_path, "a+", encoding="utf-8")
        self.load_from_file()

    def load_from_file(self) -> bool:
        """Replay the log file from the start into ``data_dict``.

        Stops at the first line that is not valid JSON (a torn final line),
        discarding it and everything after. Afterward ``log_length`` marks how
        many records were already persisted, so only new records get flushed.

        :return: The success of loading the replay file.
        """
        self.replay_file.seek(0)  # "a+" opens at EOF; replay must read from the start
        with open(self.replay_path, "rb") as byte_file:
            raw = byte_file.read()

        offset = 0  # byte offset just past the last complete, valid record
        for line in raw.split(b'\n'):
            if line == b'':
                break
            try:
                self.do_operation(json.loads(line))
                offset += len(line) + 1  # +1 for the '\n'
            except JSONDecodeError:
                break

        torn = offset < len(raw)
        if torn:
            # Truncate the fragment (and anything after it) so the file ends
            # cleanly after the last valid record; otherwise the next append
            # would merge onto the torn line and be lost on reopen.
            with open(self.replay_path, "r+b") as byte_file:
                byte_file.truncate(offset)

        self.log_length = len(self.records)  # these records are already persisted
        return not torn

    def do_operation(self, operation):
        """Execute one database operation given as a dict or a JSON string.

        ``put`` and ``del`` mutate the database and append to the pending
        record list; ``get`` is read-only and writes nothing to the log.

        :param operation: A dict (or JSON string) with an ``op`` key —
            ``put`` (``k``, ``v``), ``del`` (``k``) or ``get`` (``k``).
        :return: The result of the underlying do_put/do_del/do_get call.
        :raises ValueError: If the operation is not valid JSON or has an
            unknown ``op``.
        """
        if not isinstance(operation, dict):
            record = json.loads(operation)
        else:
            record = operation

        if record["op"] == "put":
            self.records.append(record)
            key = record["k"]
            value = record["v"]
            return self.do_put(key, value)
        elif record["op"] == "del":
            self.records.append(record)
            key = record["k"]
            return self.do_del(key)
        elif record["op"] == "get":
            key = record["k"]
            return self.do_get(key)

        raise ValueError

    def commit(self):
        """Append all pending records to the log file and flush it to disk.

        This is the commit point: a record mutated in memory only survives a
        crash or reopen once it has been flushed. Already-persisted records
        (up to ``log_length``) are never written twice.
        """
        while self.log_length < len(self.records):
            string_record = json.dumps(self.records[self.log_length])
            self.replay_file.write(string_record + '\n')
            self.log_length += 1
        self.replay_file.flush()

    def do_put(self, key, value):
        """Store ``value`` under ``key``, overwriting any existing value.

        :param key: Database key (anything JSON-serializable).
        :param value: Value to store (anything JSON-serializable).
        :return: The stored value.
        """
        self.data_dict[key] = value
        return self.data_dict[key]

    def do_del(self, key) -> bool:
        """Remove ``key`` and its value from the database.

        :param key: Database key.
        :return: True if the key existed and was removed, False otherwise.
        """
        try:
            del self.data_dict[key]
            return True
        except KeyError:
            return False

    def do_get(self, key):
        """Retrieve the value stored under a key.

        :param key: Database key.
        :return: The value, or None if the key is missing.
        """
        return self.data_dict.get(key)

    def compact(self):
        """Rewrite the log as one ``put`` record per live key, dropping
        tombstones and superseded records.

        Also commits: ``data_dict`` already includes unflushed mutations.

        :raises OSError: If the log directory is unwritable, the disk is full,
            or the atomic swap fails. The old log is left untouched.
        :raises TypeError: If a stored value is not JSON-serializable.
        """
        temp_name = ""
        new_records = []
        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode="w", dir=os.path.dirname(self.replay_path) or ".",
                prefix="jackdb-compact-", suffix=".json", delete=False
            )
            temp_name = temp_file.name
            try:
                for key, value in self.data_dict.items():
                    temp_record = {"op": "put", "k": key, "v": value}
                    new_records.append(temp_record)
                    temp_file.write(json.dumps(temp_record) + '\n')
                temp_file.flush()
                os.fsync(temp_file.fileno())
            finally:
                temp_file.close()
            os.replace(temp_name, self.replay_path)
        except Exception:
            if temp_name and os.path.exists(temp_name):
                os.remove(temp_name)
            raise

        self.replay_file.close()
        self.replay_file = open(self.replay_path, "a+", encoding="utf-8")
        self.records = new_records
        self.log_length = len(new_records)
