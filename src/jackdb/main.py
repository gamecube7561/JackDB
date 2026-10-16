"""Module containing the JackDB class."""
import json
import tempfile
import os
from io import TextIOWrapper
from json import JSONDecodeError
from jackdb.exceptions import JdbException

OPERATION_SPECS = {
    # op: (required fields, journaled, handler)
    "put": (("k", "v"), True, "do_put"),
    "del": (("k",), True, "do_del"),
    "get": (("k",), False, "do_get"),
    "get_many": (("k",), False, "do_get_many"),
    "set": (("k", "f", "v"), True, "do_set"),
}
OPERATION_TYPES = list(OPERATION_SPECS)


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

        self.load_from_file()

    def load_from_file(self, ) -> bool:
        """Replay the log file from the start into ``data_dict``.

        Stops at the first line that is not valid JSON (a torn final line),
        discarding it and everything after. Afterward ``log_length`` marks how
        many records were already persisted, so only new records get flushed.

        :return: The success of loading the replay file.
        """
        with open(self.replay_path, "a+", encoding="utf-8") as replay_file:
            replay_file.seek(0)  # "a+" opens at EOF; replay must read from the start
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

        Mutating operations (``put``, ``del``, ``set``) append to the pending
        record list; read operations (``get``, ``get_many``) write nothing to
        the log. Operation shape is driven by ``OPERATION_SPECS``.

        :param operation: A dict (or JSON string) with an ``op`` key —
            ``put`` (``k``, ``v``), ``del`` (``k``), ``get`` (``k``),
            ``get_many`` (``k``) or ``set`` (``k``, ``f``, ``v``).
        :return: The result of the underlying do_* handler call.
        :raises JdbException: If the operation is not valid JSON, has an
            unknown ``op`` or is missing required fields.
        """
        try:
            record = json.loads(operation) if not isinstance(operation, dict) else operation
        except JSONDecodeError as e:
            raise JdbException("Operation is not valid JSON.", 5) from e

        try:
            op_code = record["op"]
        except KeyError as e:
            raise JdbException("Can not parse operation key.", 4) from e

        spec = OPERATION_SPECS.get(op_code)
        if spec is None:
            raise JdbException("Unsupported operation type.", 3)

        fields, journaled, handler_name = spec
        args = []
        for field_name in fields:
            try:
                args.append(record[field_name])
            except KeyError as e:
                raise JdbException("Can not parse key value", 4) from e

        if journaled:
            self.records.append(record)
        return getattr(self, handler_name)(*args)

    def commit(self):
        """Append all pending records to the log file and flush it to disk.

        This is the commit point: a record mutated in memory only survives a
        crash or reopen once it has been flushed. Already-persisted records
        (up to ``log_length``) are never written twice.
        """
        with open(self.replay_path, "a+", encoding="utf-8") as replay_file:
            while self.log_length < len(self.records):
                string_record = json.dumps(self.records[self.log_length])
                replay_file.write(string_record + '\n')
                self.log_length += 1
            replay_file.flush()
            os.fsync(replay_file.fileno())

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

    def do_get_many(self, keys):
        """Retrieve values in bulk.

        :param keys: Array of database keys.
        :return: Tuple containing key and value.
        """
        results = []
        for key in keys:
            result = (key, self.data_dict.get(key))
            results.append(result)
        return results

    def do_set(self, key, field, value):
        """Set a field of an already existing entry. Allowing for partial updates.

        :param key: Database key.
        :param field: Field key.
        :param value: The value.
        :return:
        """
        try:
            db_data = self.data_dict[key]
        except KeyError as e:
            raise JdbException("Key does not exist.", 2) from e
        if not isinstance(db_data, dict):
            raise JdbException("Field must contain JSON data.", 1)
        db_data[field] = value
        self.data_dict[key] = db_data

        return self.data_dict[key]

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
            with tempfile.NamedTemporaryFile(
                    mode="w", dir=os.path.dirname(self.replay_path) or ".",
                    prefix="jackdb-compact-", suffix=".json", delete=False
            ) as temp_file:
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

        self.records = new_records
        self.log_length = len(new_records)
