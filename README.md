# JackDB

A simple embedded key-value database implemented as a Python library. No
dependencies — persistence is a JSON Lines append-only log you can read with
any text editor.

## How it works

Every mutation is appended to a log file as one JSON record per line:

```json
{"op":"put","k":"user:1","v":{"name":"Aoba","score":10}}
{"op":"del","k":"user:2"}
{"op":"put","k":"cfg","v":[1,2,3]}
```

- `put` stores a value under a key; `del` is a tombstone that removes a key.
- On open, the log is replayed in order — later records win — building an
  in-memory dictionary.
- A torn final line (e.g. from a crash mid-write) is detected and discarded;
  the database always opens to a consistent prefix of the log.

## Usage

```python
from jackdb.main import JackDB

db = JackDB("./mydb.log")       # opens (or creates) the log and replays it

db.do_operation('{"op":"put","k":"user:1","v":{"name":"Aoba","score":10}}')
db.do_operation('{"op":"get","k":"user:1"}')   # returns the value
db.do_operation('{"op":"del","k":"user:1"}')   # tombstone
db.flush_logs()                 # append pending records to the log + flush
db.replay_file.close()
```

Keys and values are anything `json.dumps` accepts (dicts, lists, strings,
numbers). On disk, tuples become lists like any JSON round-trip.

## Layout

```
src/jackdb/main.py    # JackDB: replay, operations, log flushing
tests/test_core.py    # hand-rolled test runner (pass/fail report)
tests/test_items.py   # test fixtures
```

## Development

Requires Python 3.14+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --no-editable          # install (note: use --reinstall-package JackDB
                               # after editing src/ — uv skips recopy otherwise)
uv run --no-sync python tests/test_core.py
```

## Design notes

- **Durability invariant:** a record is considered applied to memory only
  after the log write is issued; a failed write leaves memory untouched.
- **Single process.** There is no locking or multi-writer support — open one
  `JackDB` per log file per process.
- **Log growth.** Overwrites and tombstones accumulate; a `compact()` rewrite
  is the natural next step but not implemented yet.
