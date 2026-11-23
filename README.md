# JackDB

JackDB is an embedded Python key-value database backed by a JSON Lines
append-only log. Data is held in memory, replayed from disk when opened, and
persisted through explicit or automatic commits. Reads see an instance's
committed state. JackDB can compact the log and expose the database through
FastAPI size, get, put, set, and del endpoints.

[![PyPI](https://img.shields.io/pypi/v/JackDB)](https://pypi.org/project/JackDB/)
[![Pylint](https://github.com/gamecube7561/JackDB/actions/workflows/pylint.yml/badge.svg)](https://github.com/gamecube7561/JackDB/actions/workflows/pylint.yml)
[![Tests](https://github.com/gamecube7561/JackDB/actions/workflows/tests.yml/badge.svg)](https://github.com/gamecube7561/JackDB/actions/workflows/tests.yml)

## Quick Start

Requires Python 3.10+ and a Unix-like system such as Linux or macOS. File
locking uses `fcntl`, so native Windows is currently unsupported.

Install JackDB from [PyPI](https://pypi.org/project/JackDB/):

```bash
python -m pip install JackDB
```

By default, JackDB attempts to commit each write immediately.

```python
from jackdb import JackDB

with JackDB("./mydb.log") as db:
    db.do_operation({"op": "put", "k": "user:1", "v": {"name": "Aoba"}})
    db.do_operation({"op": "set", "k": "user:1", "f": "state", "v": "NY"})
    user = db.do_operation({"op": "get", "k": "user:1"})
    print(user)  # {'name': 'Aoba', 'state': 'NY'}
```

## Usage

```python
from jackdb import JackDB

with JackDB("./mydb.log", auto_commit=False) as db:
    receipt = db.do_operation({"op": "put", "k": "user:1", "v": {"name": "Aoba"}})
    print(receipt)  # {'status': 'pending'}
    db.do_operation({"op": "set", "k": "user:1", "f": "state", "v": "NY"})
    db.commit()
    user = db.do_operation({"op": "get", "k": "user:1"})
    print(user)  # {'name': 'Aoba', 'state': 'NY'}
    print(len(db))  # 1
```

`from jackdb.main import JackDB` also remains supported. Operations accept
Python dictionaries or JSON strings. Use string keys and JSON-serializable
values. Replay rejects nonempty non-string keys, even if the live write
accepted them. Tuples in values become lists after reopening.

### Constructor

```python
from jackdb import JackDB

JackDB(replay_path="./mydb.log", auto_commit=True, commit_size=1, db_name=None)
```

| Argument      | Behavior                                                                                                              |
|---------------|-----------------------------------------------------------------------------------------------------------------------|
| `replay_path` | Required nonempty string path. Creates the log if absent; its parent directory must already exist.                    |
| `auto_commit` | Enables automatic commits during `do_operation()`. Defaults to `True`.                                                |
| `commit_size` | Commits when pending records **reach** this number. The default `1` commits on the first pending mutation.            |
| `db_name`     | A nonempty name builds a FastAPI app and attaches it as `db.api`. By default, both `db_name` and `db.api` are `None`. |

### Operations

Call these through `db.do_operation(record)`:

| `op`       | Required fields      | Read result or successful commit result                                          |
|------------|----------------------|----------------------------------------------------------------------------------|
| `put`      | `k`, `v`             | Stores or overwrites a value and returns it.                                     |
| `del`      | `k`                  | Removes a key; returns `True` if present, otherwise `False`.                     |
| `get`      | `k`                  | Returns a value, or `None` when absent.                                          |
| `get_many` | `k` (a list of keys) | Returns `(key, value)` tuples in input order; missing values are `None`.         |
| `set`      | `k`, `f`, `v`        | Sets a field on an existing dictionary value and returns the updated dictionary. |

`put`, `del`, and `set` queue a copy of the operation and return
`{"status": "pending"}`, even when the call triggers an automatic commit.
`get` and `get_many` read committed values and add no records.
A stored `None` and a missing key both return `None`; use `key in db` to
check existence. The database also supports `len(db)`, `db[key]`, iteration
over keys, and `db.keys()`. `db[key]` raises `KeyError` for a missing key.
Reads return deep copies of stored values. The lower-level `do_put`, `do_del`,
and `do_set` methods operate on a supplied dictionary and bypass journaling.

### Persistence and recovery

```python
from jackdb import JackDB

db = JackDB("./mydb.log", auto_commit=False)
results = db.execute_and_commit({"op": "put", "k": "cfg", "v": [1, 2, 3]})
print(results[-1].result)  # [1, 2, 3]
```

`commit()` applies pending mutations in order to a working copy, appends
accepted records, and publishes the updated in-memory state after flushing
and syncing the log. It returns a list of `CommitQueueItem` objects in queue
order, or an empty list when there are no pending operations. Each item
exposes `.result` on success or `.error` if the operation raised
`JdbException` during application. For example, a rejected `set` is skipped
while other valid writes in the batch can still commit.

Use `execute_and_commit()` with a mutation to queue it and immediately commit
it alongside any earlier pending writes. To inspect a batch of queued writes,
disable automatic commits and inspect the result of an explicit `commit()`.
Pending writes can be lost if the process exits before committing. The
context manager commits on exit even if its body raises an exception.

The log stores one operation per line:

```jsonl
{"op":"put","k":"user:1","v":{"name":"Aoba","score":10}}
{"op":"del","k":"user:2"}
{"op":"set","k":"user:1","f":"state","v":"NY"}
```

Opening a database replays records in order, with later operations taking
precedence. Replay skips blank lines, malformed JSON, and invalid UTF-8
and continues reading later records. On open, JackDB truncates these lines
when they follow the last line that parses as JSON. This removes incomplete
final writes as well as malformed trailing lines that end with a newline.
A line that parses as JSON but is rejected during replay, such as an unknown
operation, is skipped and preserved. On open, JackDB adds a newline to a
log that lacks a final line break before replaying it.

### Compaction and concurrency

```python
from jackdb import JackDB

db = JackDB("./mydb.log", auto_commit=False)
db.compact()
```

`compact()` rewrites the log as one `put` record per live key, removing
superseded records and deletion tombstones. It includes pending mutations,
so successful compaction also persists those writes. If applying a pending
operation raises an error, compaction raises it. Use `commit()` to get
individual operation results. The replacement is written and synced in a temporary
file beside the log, installed with `os.replace()`, and followed by a directory
sync. Filesystem and serialization errors propagate to the caller.

A reentrant lock serializes `do_operation()`, `commit()`, and `compact()`
within an instance. A sidecar file at `<replay_path>.lock` serializes log
loading, commits, and compaction across cooperating processes. A commit with
pending writes replays the log if it has changed since the instance last
loaded or wrote it. Compaction always replays the latest log before applying
pending writes.

Other instances do not automatically refresh their in-memory data after a
writer commits. File locking does not make multiple operations a transaction
or provide fully synchronized reads across instances. Direct `do_*` calls
also bypass the instance lock.

### Error handling

```python
from jackdb.exceptions import JdbException
from jackdb import JackDB

try:
    db = JackDB("./mydb.log", auto_commit=False)
    db.do_operation({"op": "unknown"})
except JdbException as error:
    print(error.message, error.error_code)
```

| Error code | Cause                                           |
|------------|-------------------------------------------------|
| `1`        | `set` targets a value that is not a dictionary. |
| `2`        | `set` targets a missing key.                    |
| `3`        | Unsupported operation name.                     |
| `4`        | Missing operation key or required field.        |
| `5`        | Operation text is not valid JSON.               |
| `6`        | Database name must be set before serving API.   |
| `7`        | Replay found a nonempty non-string key.         |

An empty log path raises `ValueError`. Filesystem errors and unsupported
Python input types may raise standard exceptions; operation validation does
not cover every possible malformed input.

JackDB uses Python's standard logging. Configure the `jackdb` logger in your
application to see diagnostics for replay, commits, and compaction.

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

`GET /demo/get/{key}` returns the stored JSON value, or `null` if the key is
missing. `PUT /demo/put/{key}` accepts a body such as
`{"value": "hello"}` or `{"value": {"name": "Aoba", "score": 10}}` and
returns the stored value. `PUT /demo/set/{key}` accepts a body such as
`{"field": "score", "value": 123}`. SET adds or updates a field on an existing
JSON object and returns the updated object. A missing key or a value that is
not an object returns HTTP 409. Each successful PUT commits pending operations
before responding, regardless of `auto_commit`.

`DELETE /demo/del/{key}` takes no request body, removes the key if present,
and commits pending operations. It returns HTTP 200 with
`{"message": "Item successfully deleted.", "id": "<key>"}` even if the key
was already absent.

Both PUT endpoints require a `value` field and accept strings, integers,
fractional numbers, JSON objects, arrays, and booleans. Objects and arrays can
contain nested JSON values, including null. A top-level null or an omitted
`value` returns HTTP 422. SET also requires a string `field`; a missing field
or a non-string field returns HTTP 422. The embedded storage API additionally
supports top-level null. Keys must fit in a single URL path segment;
slash-containing keys are not supported.

`db.serve()` builds or replaces `db.api`; it does not start a server. To attach
an API later, set a nonempty `db.db_name` and call `db.serve()`. Applications
can also use `serve_routes(name, db)` from `jackdb.api` directly.

## Project layout

```text
src/jackdb/__init__.py    # Public JackDB export and version
src/jackdb/main.py        # Public JackDB subclass and API attachment
src/jackdb/core.py        # Storage, replay, operations, commit, compaction
src/jackdb/api.py         # FastAPI application and routes
src/jackdb/api_models.py  # Models for FastAPI
src/jackdb/operations.py  # Operation specifications and validation
src/jackdb/commit_record.py  # Queued operations and commit results
src/jackdb/logger.py      # Library logger
src/jackdb/exceptions.py  # JdbException
tests/test_core.py       # Custom runner with 24 database/API checks
tests/test_items.py      # Test data
```

The dependency graph is `main → api → core`, with `main → core` as well.
The API accepts the core `JackDB` type, and the public class inherits its
database methods. The core module has no dependency on the API layer.

## Development

To install from a local checkout, run `python -m pip install .` from the
repository root. `pyproject.toml` declares `fastapi[standard]` and
`pydantic` as dependencies. FastAPI's standard extras include Uvicorn.
`requirements.txt` contains an exported, pinned dependency set.

Run commands from the repository root. With [uv](https://docs.astral.sh/uv/):

```bash
uv sync
PYTHONPATH=src uv run --no-sync python tests/test_core.py
```

Setting `PYTHONPATH=src` ensures tests use the checkout, including on systems
where editable-install discovery is unreliable. The custom runner prints
passed and failed counts and exits with status 1 if any check fails.

To run the same lint command as GitHub Actions:

```bash
python -m pip install pylint .
pylint $(git ls-files '*.py')
```

GitHub Actions runs Pylint on pushes for Python 3.10 through 3.14.

After changing dependencies in `pyproject.toml`, update the lockfile and
regenerate the requirements export. The lockfile is local and ignored by Git.

```bash
uv lock
uv export --locked --no-dev --no-emit-project --no-hashes -o requirements.txt
```

Keep `pyproject.toml` as the source of dependency declarations and regenerate
`requirements.txt` instead of editing the export by hand.
