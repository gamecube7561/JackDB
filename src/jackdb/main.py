import json
import sys
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

    def load_from_file(self):
        """Replay the log file from the start into ``data_dict``.

        Stops at the first line that is not valid JSON (a torn final line),
        discarding it and everything after. Afterward ``log_length`` marks how
        many records were already persisted, so only new records get flushed.
        """
        self.replay_file.seek(0)  # "a+" opens at EOF; replay must read from the start
        for line in self.replay_file:
            try:
                record = json.loads(line)
                self.do_operation(record)
            except JSONDecodeError:
                break

        self.log_length = len(self.records)

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
