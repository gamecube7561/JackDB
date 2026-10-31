# JackDB

JackDB is an embedded Python key-value database backed by a JSON Lines
append-only log. Data is held in memory, replayed from disk when opened, and
persisted through explicit or automatic commits. A FastAPI integration exposes
a size endpoint.

## Installation

Requires Python 3.10+ and a Unix-like system such as Linux or macOS. File
locking uses `fcntl`, so native Windows is currently unsupported.

From the repository root:

```bash
python -m pip install .
```

The project declares `fastapi[standard]` as a dependency. This also installs
Uvicorn and FastAPI's standard extras. `requirements.txt` contains an exported,
pinned dependency set; installing the project itself uses `pyproject.toml`.

## Usage

```python
from jackdb import JackDB

with JackDB("./mydb.log", auto_commit=False) as db:
    db.do_operation({"op": "put", "k": "user:1", "v": {"name": "Aoba"}})
    db.do_operation({"op": "set", "k": "user:1", "f": "state", "v": "NY"})
    user = db.do_operation({"op": "get", "k": "user:1"})
    print(user)  # {'name': 'Aoba', 'state': 'NY'}
    print(len(db))  # 1
# Leaving the context commits pending operations.
```

`from jackdb.main import JackDB` also remains supported. Operations accept
Python dictionaries or JSON strings. Use string keys for predictable JSON
round trips and JSON-serializable values. Lists and dictionaries cannot be
keys; tuples in values become lists after reopening.

### Constructor

```python
JackDB(replay_path="", auto_commit=True, commit_size=10, db_name="")
```

| Argument | Behavior |
| --- | --- |
| `replay_path` | Required nonempty string path. Creates the log if absent; its parent directory must already exist. |
| `auto_commit` | Enables automatic commits during `do_operation()`. Defaults to `True`. |
| `commit_size` | Commits when pending records **exceed** this number. The default `10` commits on the 11th pending mutation. |
| `db_name` | A nonempty name builds a FastAPI app and attaches it as `db.api`. Defaults to an empty string, leaving `db.api` as `None`. |

### Operations

Call these through `db.do_operation(record)`:

| `op` | Required fields | Result |
| --- | --- | --- |
| `put` | `k`, `v` | Stores or overwrites a value and returns it. |
| `del` | `k` | Removes a key; returns `True` if present, otherwise `False`. |
| `get` | `k` | Returns a value, or `None` when absent. |
| `get_many` | `k` (a list of keys) | Returns `(key, value)` tuples in input order; missing values are `None`. |
| `set` | `k`, `f`, `v` | Sets a field on an existing dictionary value and returns the updated dictionary. |

`put`, `del`, and `set` are journaled. `get` and `get_many` add no records.
A stored `None` and a missing key both return `None`; use `key in db` to
check existence. The database also supports `len(db)`, `db[key]`, iteration
over keys, and `db.keys()`. `db[key]` raises `KeyError` for a missing key.

The lower-level `do_put`, `do_del`, and `do_set` methods change memory directly
without journaling. Use `do_operation()` for mutations that must survive a
normal commit and reopen. Likewise, edit stored objects through operations
rather than mutating returned dictionaries or lists directly.

### Persistence and recovery

```python
db = JackDB("./mydb.log", auto_commit=False)
db.do_operation({"op": "put", "k": "cfg", "v": [1, 2, 3]})
db.commit()
```

Mutations first update memory and queue operation records. `commit()` appends
pending records, flushes the file, and calls `os.fsync()`. Commit explicitly
before relying on durability; pending operations may be lost if the process
exits without committing. The context manager commits on exit, including
when its body raises an exception; it does not provide rollback.

The log stores one operation per line:

```jsonl
{"op":"put","k":"user:1","v":{"name":"Aoba","score":10}}
{"op":"del","k":"user:2"}
{"op":"set","k":"user:1","f":"state","v":"NY"}
```

Opening a database replays records in order, with later operations taking
precedence. Replay stops at a blank line or invalid JSON and truncates the
remaining bytes. This recovers from an incomplete final write, but it is not
a general corruption-repair mechanism: invalid operation records can still
raise errors, and content after the stopping point is discarded.

### Compaction and concurrency

```python
db.compact()
```

`compact()` rewrites the log as one `put` record per live key, removing
superseded records and deletion tombstones. It includes pending mutations,
so it also commits. The replacement is written and synced in a temporary
file beside the log, installed with `os.replace()`, and followed by a directory
sync. Filesystem and serialization errors propagate to the caller.

A reentrant lock serializes `do_operation()`, `commit()`, and `compact()`
within an instance. A sidecar file at `<replay_path>.lock` serializes log
loading, commits, and compaction across cooperating processes. Compaction
replays the latest log before applying the instance's pending operations.

Other instances do not automatically refresh their in-memory data after a
writer commits. File locking does not make multiple operations a transaction
or provide fully synchronized reads across instances. Direct `do_*` calls
also bypass the instance lock.

### Error handling

```python
from jackdb.exceptions import JdbException

try:
    db.do_operation({"op": "unknown"})
except JdbException as error:
    print(error.message, error.error_code)
```

| Error code | Cause |
| --- | --- |
| `1` | `set` targets a value that is not a dictionary. |
| `2` | `set` targets a missing key. |
| `3` | Unsupported operation name. |
| `4` | Missing operation key or required field. |
| `5` | Operation text is not valid JSON. |

An empty log path raises `ValueError`. Filesystem errors and unsupported
Python input types may raise standard exceptions; operation validation does
not cover every possible malformed input.

## HTTP API

A named database attaches a FastAPI application. To run it with Uvicorn:

```python
from jackdb import JackDB
import uvicorn

if __name__ == "__main__":
    db = JackDB("./mydb.log", db_name="demo")
    uvicorn.run(db.api, host="127.0.0.1", port=8000)
```

`GET http://127.0.0.1:8000/demo/size` returns the current number of keys as a
JSON integer. FastAPI's interactive documentation is available at `/docs`.
The size route is currently the only database HTTP endpoint.

`db.serve()` builds or replaces `db.api`; it does not start a server. To attach
an API later, set a nonempty `db.db_name` and call `db.serve()`. Applications
can also use `serve_routes(name, db)` from `jackdb.api` directly.

## Project layout

```text
src/jackdb/__init__.py    # Public JackDB export and version
src/jackdb/main.py        # Public JackDB subclass and API attachment
src/jackdb/core.py        # Storage, replay, operations, commit, compaction
src/jackdb/api.py         # FastAPI application and routes
src/jackdb/operations.py  # Operation specifications and validation
src/jackdb/exceptions.py  # JdbException
tests/test_core.py       # Custom runner with 13 database/API checks
tests/test_items.py      # Test data
```

The dependency graph is `main → api → core`, with `main → core` as well.
The API accepts the core `JackDB` type, and the public class inherits its
database methods. The core module has no dependency on the API layer.

## Development

Run commands from the repository root. With [uv](https://docs.astral.sh/uv/):

```bash
uv sync
PYTHONPATH=src uv run --no-sync python tests/test_core.py
```

Setting `PYTHONPATH=src` ensures tests use the checkout, including on systems
where editable-install discovery is unreliable. The custom runner prints
passed and failed counts; inspect that report, since failed checks do not
currently produce a nonzero process exit status.

To run the same lint command as GitHub Actions:

```bash
python -m pip install pylint .
pylint $(git ls-files '*.py')
```

GitHub Actions runs Pylint on pushes for Python 3.10 through 3.14.

After changing dependencies in `pyproject.toml`, update the lockfile and
regenerate the requirements export:

```bash
uv lock
uv export --locked --no-dev --no-emit-project --no-hashes -o requirements.txt
```

Keep `pyproject.toml` as the source of dependency declarations and regenerate
`requirements.txt` instead of editing the export by hand.
