"""Database storage and operations, independent of the API layer."""
import json
import tempfile
import os
import fcntl
import threading
from contextlib import contextmanager
from copy import deepcopy
from io import TextIOWrapper
from json import JSONDecodeError
from jackdb.exceptions import JdbException
from jackdb.operations import _resolve
from jackdb.commit_record import CommitQueueItem


class JackDB:
    """An embedded key-value database backed by a JSON Lines append-only log.

    Every mutation (``put``/``del``) is recorded in memory and appended to the
    log file when :meth:`flush_logs` is called. On open, the log is replayed in
    order (later records win) to rebuild the in-memory dictionary; a torn final
    line from a crash mid-write is discarded, so the database always opens to a
    consistent prefix of the log.

    Writers on the same log file are serialized across processes by an
    exclusive ``flock`` on a sidecar lock file (``replay_path + ".lock"``).
    """

    def __init__(self, replay_path: str = "", auto_commit: bool = True,
                 commit_size: int = 1, db_name: None | str = None):
        """Open (or create) the log file and replay it into memory.

        :param replay_path: Path to the JSON Lines log file. Required.
        :param auto_commit: Whether autocommit is enabled or not.
        :param commit_size: Size of uncommitted logs before auto committing.
        :raises ValueError: If ``replay_path`` is empty.
        """
        self.replay_file: TextIOWrapper
        self.data_dict = {}
        self.replay_path = replay_path
        self.records = []
        self.log_length = 0
        self.auto_commit = auto_commit
        self.commit_size = commit_size
        self.db_name = db_name

        self._log_version = None
        self._lock = threading.RLock()

        if self.replay_path == "":
            raise ValueError("replay_path is required")

        self.load_from_file()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.commit()
        return False

    def __len__(self):
        return len(self.data_dict)

    def __contains__(self, item):
        return item in self.data_dict

    def __iter__(self):
        return iter(self.data_dict)

    def __getitem__(self, key):
        return deepcopy(self.data_dict[key])

    def keys(self):
        """
        Return a set of the keys from the data dict.
        :return:
        """
        return self.data_dict.keys()

    @contextmanager
    def _log_lock(self):
        """Exclusive lock on a sidecar lock file, serializing ``commit`` and
        ``compact`` across processes.

        The lock lives on ``replay_path + ".lock"`` — a path that is never
        replaced — because ``compact`` swaps the log's inode via ``os.replace``,
        so a lock held on the log file itself would not exclude writers that
        open the new inode.
        """
        with open(self.replay_path + ".lock", "a+", encoding='utf-8') as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def load_from_file(self) -> bool:
        """Replay the log file from the start into ``data_dict``.

        Invalid records are skipped.

        A torn final line (and anything after it) is discarded and truncated
        away so the next append cannot merge onto it. Afterward ``log_length``
        marks how many records were already persisted, so only new records get
        flushed.

        Holds the log lock while reading and truncating: a concurrent commit's
        partially written line must not be mistaken for a torn tail and cut
        away (the writer already counted it as persisted).

        :return: The success of loading the replay file.
        """
        with self._log_lock():
            if not self.has_new_line():
                self.add_new_line()

            self.records = []  # rebuilt below: ``records`` mirrors the file
            data_dict = {}
            self.log_length, torn, _ = self._replay_log(data_dict, journal=True)
            self.data_dict = data_dict
            self._log_version = self._file_version(os.stat(self.replay_path))
            return not torn

    @staticmethod
    def _file_version(stat: os.stat_result) -> tuple:
        """Identify the log and detect changes made by cooperating writers."""
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    def _replay_log(self, db: dict, journal: bool = False) -> tuple:
        """Apply every complete, valid record in the log file to ``data_dict``.

        Stops at the first line that is not valid JSON (a torn final line);
        the fragment and everything after it is truncated away so the file ends
        cleanly after the last valid record.

        :param db: Database to use.
        :param journal: When True (initial load), also append each record to
            ``records`` so the in-memory bookkeeping mirrors the file — this is
            what keeps ``log_length`` aligned and stops ``commit`` from
            re-writing or skipping already-persisted records. Compaction
            replays with journal=False and tracks its own pending slice.
        :return: Tuple of (number of records applied, whether a torn tail was
            found and truncated).
        """
        with open(self.replay_path, "rb") as byte_file:
            raw = byte_file.read()

        offset = 0  # byte offset just past the last complete, valid record
        count = 0
        bad_records = []
        tail_offset = 0

        for line in raw.split(b'\n'):
            offset += len(line) + 1  # +1 for the '\n'

            try:
                record = json.loads(line)
            except (JSONDecodeError, UnicodeDecodeError):
                continue

            tail_offset = offset

            try:
                self._apply(db, record)
                if journal:
                    self.records.append(record)
                count += 1
            except (JdbException, TypeError):
                bad_records.append(record)
                continue

        torn = tail_offset < len(raw)
        if torn:
            with open(self.replay_path, "r+b") as byte_file:
                byte_file.truncate(tail_offset)
        return count, torn, bad_records

    def _apply(self, db: dict, record):
        """Validate and execute one operation record without journaling it.

        Used for log replay, where the record is already persisted.

        :param db: Database to use.
        :return: The result of the underlying do_* handler call.
        """
        _, handler_name, args = _resolve(record)
        if args[0] and not isinstance(args[0], str):
            raise JdbException("Operation key field must be of type str.", 7)
        args = [db] + args
        return getattr(self, handler_name)(*args)

    def execute_and_commit(self, operation) -> list[CommitQueueItem]:
        """
        Execute, commit, and returns a list of the mutating operation results.
        :param operation: A dict (or JSON string) with an ``op`` key —
            ``put`` (``k``, ``v``), ``del`` (``k``), ``get`` (``k``),
            ``get_many`` (``k``) or ``set`` (``k``, ``f``, ``v``).
        :return:
        """
        with self._lock:
            try:
                record = json.loads(operation) if not isinstance(operation, dict) else operation
            except JSONDecodeError as e:
                raise JdbException("Operation is not valid JSON.", 5) from e

            journaled, handler_name, args = _resolve(record)
            if journaled:
                self._enqueue(handler_name, args, record)
            results = self.commit()
            return results

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
        with self._lock:
            try:
                record = json.loads(operation) if not isinstance(operation, dict) else operation
            except JSONDecodeError as e:
                raise JdbException("Operation is not valid JSON.", 5) from e

            journaled, handler_name, args = _resolve(record)

            if journaled:
                self._enqueue(handler_name, args, record)
                result = {"status": "pending"}
                # Placed in this block so only mutating operations trigger auto commit.
                if self.auto_commit and self.log_length <= (len(self.records) - self.commit_size):
                    self.commit()
            else:
                result = getattr(self, handler_name)(*args)

            return result

    def _enqueue(self, handler_name, args, record):
        # Deep copy to prevent the record being changed as easily
        item = deepcopy(CommitQueueItem(handler_name, args, record))
        self.records.append(item)
        return item

    def do_put(self, db: dict, key: str, value):
        """Store ``value`` under ``key``, overwriting any existing value.

        :param db: Database to use.
        :param key: Database key.
        :param value: Value to store (anything JSON-serializable).
        :return: The stored value.
        """
        db[key] = value
        return deepcopy(db[key])

    def do_del(self, db: dict, key: str) -> bool:
        """Remove ``key`` and its value from the database.

        :param db: Database to use.
        :param key: Database key.
        :return: True if the key existed and was removed, False otherwise.
        """
        try:
            del db[key]
            return True
        except KeyError:
            return False

    def do_get(self, key: str):
        """Retrieve the value stored under a key.

        :param key: Database key.
        :return: The value, or None if the key is missing.
        """
        return deepcopy(self.data_dict.get(key))

    def do_get_many(self, keys: list[str]):
        """Retrieve values in bulk.

        :param keys: Array of database keys.
        :return: A list of tuples containing key and value.
        """
        results = []
        for key in keys:
            result = deepcopy((key, self.data_dict.get(key)))
            results.append(result)
        return results

    def do_set(self, db: dict, key: str, field, value):
        """Set a field of an already existing entry. Allowing for partial updates.

        :param db: Database to use.
        :param key: Database key.
        :param field: Field key.
        :param value: The value.
        :return:
        """
        try:
            db_data = db[key]
        except KeyError as e:
            raise JdbException("Key does not exist.", 2) from e
        if not isinstance(db_data, dict):
            raise JdbException("Field must contain JSON data.", 1)

        db_data[field] = value
        db[key] = db_data

        return deepcopy(db[key])

    def commit(self) -> list[CommitQueueItem]:
        """Append all pending records to the log file and flush it to disk.

        This is the commit point: a record mutated in memory only survives a
        crash or reopen once it has been flushed. Already-persisted records
        (up to ``log_length``) are never written twice.
        """
        with self._lock:
            # No record changes
            if self.log_length == len(self.records):
                return []

            with self._log_lock(), open(self.replay_path, "a+b", buffering=0) as replay_file:
                # Reuse the cached state only while it matches the current log.
                log_stat = os.fstat(replay_file.fileno())

                if self._file_version(log_stat) == self._log_version:
                    # Our version of the dict is the most current
                    data_dict_copy = deepcopy(self.data_dict)
                else:
                    # Our dict has been modified, and must reload it from file
                    data_dict_copy = {}
                    self._replay_log(data_dict_copy)
                    log_stat = os.fstat(replay_file.fileno())

                log_offset = self.log_length
                original_file_size = log_stat.st_size
                results = []
                encoded_strings = []
                try:
                    pending_records = []

                    # Create our pending records queue
                    while log_offset < len(self.records):
                        record: CommitQueueItem = self.records[log_offset]
                        string_record = json.dumps(record.record) + '\n'
                        encoded_string = string_record.encode('utf-8')
                        pending_records.append((record, encoded_string))
                        log_offset += 1

                    # Apply the record to the temp dict and add results to the record
                    for record, encoded_string in pending_records:
                        try:
                            result = getattr(self, record.handler)(data_dict_copy, *record.args)
                            # Check the amount of bytes written versus string length
                            record.result = result
                            results.append(record)
                            encoded_strings.append(encoded_string)
                        except JdbException as e:
                            record.set_error(e)
                            results.append(record)
                            continue

                    # Write to log file
                    for encoded_string in encoded_strings:
                        written_bytes = replay_file.write(encoded_string)
                        # Check whether all bytes were written
                        if written_bytes != len(encoded_string):
                            raise OSError(f"Short journal write: "
                                          f"wrote {written_bytes} of "
                                          f"{len(encoded_string)} bytes")

                    # Apply the changes
                    replay_file.flush()
                    os.fsync(replay_file.fileno())
                    self._log_version = self._file_version(os.fstat(replay_file.fileno()))
                    self.data_dict = data_dict_copy
                except OSError:
                    # Rollback the file
                    os.ftruncate(replay_file.fileno(), original_file_size)
                    os.fsync(replay_file.fileno())
                    raise
                self.log_length = log_offset
                return results

    def compact(self):
        """Rewrite the log as one ``put`` record per live key, dropping
        tombstones and superseded records.

        Also commits: ``data_dict`` already includes unflushed mutations.

        Holds the log lock for the whole rewrite and first replays everything
        already committed to the file — including records written by other
        processes since this instance opened — so the swap cannot drop records
        it never saw.

        :raises OSError: If the log directory is unwritable, the disk is full,
            or the atomic swap fails. The old log is left untouched.
        :raises TypeError: If a stored value is not JSON-serializable.
        """
        with self._lock:
            temp_name = ""
            new_records = []
            with self._log_lock():
                # Rebuild in-memory state from the file as it exists right now,
                # then re-apply this instance's still-pending mutations on top
                # (this instance commits last, so its pending records win).
                pending = self.records[self.log_length:]
                pending_dict_copy = {}
                self._replay_log(pending_dict_copy)

                for record in pending:
                    handler = record.handler
                    args = record.args
                    getattr(self, handler)(pending_dict_copy, *args)

                dir_fd = os.open(os.path.dirname(self.replay_path) or '.', os.O_RDONLY)
                try:
                    with tempfile.NamedTemporaryFile(
                            mode="w", dir=os.path.dirname(self.replay_path) or ".",
                            prefix="jackdb-compact-", suffix=".json", delete=False
                    ) as temp_file:
                        temp_name = temp_file.name

                        for key, value in pending_dict_copy.items():
                            temp_record = {"op": "put", "k": key, "v": value}
                            new_records.append(temp_record)
                            temp_file.write(json.dumps(temp_record) + '\n')
                        temp_file.flush()
                        os.fsync(temp_file.fileno())
                        os.replace(temp_name, self.replay_path)
                        os.fsync(dir_fd)
                        self._log_version = self._file_version(os.fstat(temp_file.fileno()))
                except Exception:
                    if temp_name and os.path.exists(temp_name):
                        os.remove(temp_name)
                    raise
                finally:
                    os.close(dir_fd)
                self.data_dict = pending_dict_copy

                self.records = new_records
                self.log_length = len(new_records)

    def has_new_line(self):
        """
        Check whether a file has a new line at the end of it.
        :return: Bool: If a new line is found at the end of the file.
        """
        with open(self.replay_path, 'a+', encoding='utf-8') as f:
            try:
                # Move the file pointer to 1 byte before the end of the file
                f.seek(-1, 2)
                last_char = f.read(1)
                return last_char == b'\n'
            except OSError:
                # The file is likely empty
                return False

    def add_new_line(self):
        """
        Add a new line to the end of a file.
        :return:
        """
        with open(self.replay_path, "a+", encoding='utf-8') as f:
            f.write("\n")
