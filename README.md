# JackDB

A simple embedded key-value database implemented as a Python library. No
dependencies — persistence is a JSON Lines append-only log you can read with
any text editor.

## How it works

Every mutation is appended to a log file as one JSON record per line:

```json lines
{"op":"put","k":"user:1","v":{"name":"Aoba","score":10}}
{"op":"del","k":"user:2"}
{"op":"put","k":"cfg","v":[1,2,3]}
{"op":"set","k":"user:1","f":"state","v":"NY"}
```

- `put` stores a value under a key.
- `del` is a tombstone that removes a key.
- `get` is read-only — it never writes to the log.
- `set` stores a value in a specific field of an already populated key.
- On open, the log is replayed in order — later records win — building an
  in-memory dictionary.
- A torn final line (e.g. from a crash mid-write) is detected, discarded, and
  truncated away, so the log always ends cleanly after the last valid record;
  the database always opens to a consistent prefix of the log.

## Usage

```python
from jackdb.main import JackDB

db = JackDB(replay_path="./mydb.log", auto_commit=True, commit_size=10)  # opens (or creates) the log and replays it

db.do_operation('{"op":"put","k":"user:1","v":{"name":"Aoba","score":10}}')
db.do_operation('{"op":"get","k":"user:1"}')  # returns the value (None if missing)
db.do_operation('{"op":"set","k":"user:1","f":"state","v":"NY"}') # sets value of the state field in user:1
db.do_operation('{"op":"del","k":"user:1"}')  # tombstone
db.commit()  # append pending records to the log + flush
```

Keys and values are anything `json.dumps` accepts (dicts, lists, strings,
numbers). On disk, tuples become lists like any JSON round-trip.

### Error handling

- `JackDB("")` raises `ValueError` — a log path is required.
- An operation with an unknown `op` raises `ValueError`.
- `do_get` returns `None` for a missing key; a stored empty string is
  distinguishable from absence.

### Compaction

Overwrites and tombstones accumulate in the log. `compact()` rewrites it as
one `put` record per live key:

```python
db.compact()
```

The rewrite is atomic: the compacted log is built in a temporary file next to
the log, fsynced, and swapped in with `os.replace` — a crash leaves either the
old log or the full compacted one. Compaction also commits: unflushed
in-memory mutations are included, and on any failure the old log is left
untouched and the error re-raised (`OSError` for filesystem problems,
`TypeError` for unserializable values).

## Layout

```
src/jackdb/main.py    # JackDB: replay, operations, commit, compaction
tests/test_core.py    # hand-rolled test runner (pass/fail report)
tests/test_items.py   # test fixtures
```

## Development

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --no-editable          # install (note: use --reinstall-package JackDB
                               # after editing src/ — uv skips recopy otherwise)
uv run --no-sync python tests/test_core.py
```

## Design notes

- **Durability invariant:** in-memory mutations survive a crash or reopen
  only after `commit()` — that call is the commit point.
- **Bookkeeping invariant:** `records` mirrors the log (plain record dicts),
  and `log_length` marks how many are already persisted, so `commit()` never
  writes a record twice.
- **Single process.** There is no locking or multi-writer support — open one
  `JackDB` per log file per process.
