"""Driver for the tests."""
import os
import tempfile
import json
import shutil
from pathlib import Path
from unittest.mock import patch
import test_items
from fastapi.testclient import TestClient
from jackdb import JackDB
from jackdb.exceptions import JdbException
from jackdb.api import serve_routes


def init_test():
    """
    Initialize the test text file
    :return:
    """
    shutil.copy('./tests/test_file1.txt', './tests/test.txt')


def init_test2():
    """
    Initialize the test text file
    :return:
    """
    shutil.copy('./tests/test_file1_no_new_line.txt', './tests/test.txt')


def teardown_test():
    """
    Test Cleanup.
    :return:
    """
    Path('./tests/test.txt.lock').unlink(missing_ok=True)
    Path('./tests/test.txt').unlink(missing_ok=True)


def test1():
    """
    Test 1: File loading
    :return:
    """
    init_test()
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as temp_file:
        temp_text = json.dumps(test_items.TEST_PUT_DATA)
        temp_file.write(temp_text)
        temp_file.flush()
        jdb = JackDB(str(temp_file.name))
        if jdb.records[0] != test_items.TEST_PUT_DATA:
            print(f"Test 3 \nexpected: {test_items.TEST_PUT_DATA}\ngot: {jdb.records[0]}")
            return False
        return True


def test2():
    """
    Test 2: More advanced file loading
    :return:
    """
    init_test()
    jdb = JackDB('./tests/test.txt')
    if jdb.data_dict != test_items.TEST_PUT_OUTPUT:
        print(f"Test 2 \nexpected: {test_items.TEST_PUT_OUTPUT}\ngot: {jdb.data_dict}")
        return False
    return True


def test3():
    """
    Test 3: Performing operation and commiting to log.
    :return:
    """
    init_test()
    jdb = JackDB('./tests/test.txt')
    jdb.do_operation(json.dumps(test_items.TEST_PUT_DATA2))
    jdb.commit()

    # Acceptance: flushed record survives reopen (log-before-apply consistency)
    reopened = JackDB('./tests/test.txt')
    expected = dict(test_items.TEST_PUT_OUTPUT)
    expected['user:3'] = test_items.TEST_PUT_DATA2['v']

    if reopened.data_dict != expected:
        print(f"Test 3 \nexpected: {expected}\ngot: {reopened.data_dict}")
        return False
    return True


def test4():
    """
    Test 4: compact output where later entries should supersede previous entries with the same key.
    :return:
    """
    init_test()
    jdb = JackDB('./tests/test.txt')
    jdb.do_operation(json.dumps(test_items.TEST_PUT_DATA2))
    jdb.do_operation(json.dumps(test_items.TEST_PUT_DATA3))

    # Acceptance: the second put operation will supersede in the compacted log
    jdb.commit()
    jdb.compact()

    reopened = JackDB('./tests/test.txt')
    expected = dict(test_items.TEST_PUT_OUTPUT2)

    if reopened.data_dict != expected:
        print(f"Test 4 \nexpected: {expected}\ngot: {reopened.data_dict}")
        return False
    return True


def test5():
    """
    Test 5: Using the set option.
    :return:
    """
    init_test()
    jdb = JackDB('./tests/test.txt')
    jdb.do_operation(json.dumps(test_items.TEST_PUT_DATA2))
    jdb.do_operation(json.dumps(test_items.TEST_PUT_DATA3))
    jdb.do_operation(json.dumps(test_items.TEST_SET_DATA1))

    expected = dict(test_items.TEST_PUT_OUTPUT3)
    if jdb.data_dict != expected:
        print(f"Test 5 \nexpected: {expected}\ngot: {jdb.data_dict}")
        return False
    return True


def test6():
    """
    Test 6: Using the get_many option.
    :return:
    """
    init_test()
    jdb = JackDB('./tests/test.txt')
    jdb.do_operation(json.dumps(test_items.TEST_PUT_DATA2))
    jdb.do_operation(json.dumps(test_items.TEST_PUT_DATA3))
    jdb.do_operation(json.dumps(test_items.TEST_SET_DATA1))

    expected = [('user:1', test_items.TEST_PUT_OUTPUT3['user:1']),
                ('user:3', test_items.TEST_PUT_OUTPUT3['user:3'])]
    result = jdb.do_operation(test_items.TEST_GET_MANY1)
    if result != expected:
        print(f"Test 6 \nexpected: {expected}\ngot: {result}")
        return False
    return True


def test7():
    """
    Test 7: Bad operation error handling.
    :return:
    """
    init_test()
    jdb = JackDB('./tests/test.txt')
    try:
        jdb.do_operation(json.dumps(test_items.TEST_BAD_OPERATION))
    except JdbException:
        return True
    return False


def test8():
    """
    Test 8: Allow to open JackDB using with-as.
    :return:
    """
    init_test()
    try:
        with JackDB('./tests/test.txt') as jdb:
            jdb.do_operation(json.dumps(test_items.TEST_PUT_DATA2))
            jdb.do_operation(json.dumps(test_items.TEST_PUT_DATA3))

            jdb.commit()
            jdb.compact()

            return True
    except JdbException:
        return False


def test9():
    """
    Test 9: Test the dunders.
    :return:
    """
    init_test()
    try:
        jdb = JackDB('./tests/test.txt')
        j_len = len(jdb)

        return j_len == 2 and 'cfg' in jdb
    except JdbException:
        return False


def test10():
    """
    Test 10: Iteration dunder reflects the replayed log.
    :return:
    """
    init_test()
    jdb = JackDB('./tests/test.txt')
    jdb.do_operation(json.dumps(test_items.TEST_PUT_DATA3))
    jdb.commit()

    reopened = JackDB('./tests/test.txt')
    keys = list(reopened)  # exercises __iter__

    if sorted(keys) != sorted(test_items.TEST_PUT_OUTPUT2.keys()):
        print(f"Test 10 \nexpected keys: {sorted(test_items.TEST_PUT_OUTPUT2.keys())}"
              f"\ngot: {sorted(keys)}")
        return False

    return dict(reopened) == dict(test_items.TEST_PUT_OUTPUT2)


def test11():
    """
    Test 11: Many puts and autocommit.
    :return:
    """
    init_test()
    try:
        with JackDB('./tests/test.txt') as jdb:
            for i in range(1, 100):
                op = {
                    'op': 'put',
                    'k': f'user:{i + 100}',
                    'v': {
                        'name': 'Aoba',
                        'score': f'{i}'
                    }
                }
                jdb.do_operation(json.dumps(op))
            return len(jdb) == 101
    except JdbException:
        return False


def test12():
    """
    Test 12: Named DB.
    :return:
    """
    init_test()
    try:
        JackDB('./tests/test.txt', db_name="Test")
    except JdbException:
        return False
    return True


def test13():
    """
    Test 13: The API reports the record count at /{db_name}/size.
    :return:
    """
    init_test()
    try:
        jdb = JackDB('./tests/test.txt')
        app = serve_routes('Test', jdb)

        client = TestClient(app)
        response = client.get('/Test/size')

        if response.status_code != 200 or response.json() != len(jdb):
            print(f"Test 13 \nexpected: 200 {len(jdb)}\n"
                  f"got: {response.status_code} {response.text}")
            return False
        return True
    except JdbException:
        return False


def test14():
    """
    Test 14: When file doesn't have new line at the end
    :return:
    """
    init_test2()
    try:
        jdb = JackDB('./tests/test.txt')
        app = serve_routes('Test', jdb)

        client = TestClient(app)
        response = client.get('/Test/size')

        if response.status_code != 200 or response.json() != len(jdb):
            print(f"Test 14 \nexpected: 200 {len(jdb)}\n"
                  f"got: {response.status_code} {response.text}")
            return False
        return True
    except JdbException as e:
        print(e)
        return False


def test15():
    """
    Test 15: API get test.
    :return:
    """
    init_test()
    jdb = JackDB('./tests/test.txt')
    app = serve_routes('Test', jdb)

    client = TestClient(app)
    response = client.get('/Test/get/user:1')

    if response.status_code != 200:
        print("Response code not 200")
        return False
    if response.text != """{"name":"Aoba","score":10}""":
        print("Result not correct")
        return False
    return True


def test16():
    """
    Test 16: API put test.
    :return:
    """
    init_test()
    jdb = JackDB('./tests/test.txt')
    app = serve_routes('Test', jdb)

    client = TestClient(app)
    input_data = {"value": {"name": "Aoba", "score": 123}}
    put_resp = client.put('Test/put/user:1', json=input_data)
    get_resp = client.get('/Test/get/user:1')

    if get_resp.status_code != 200 or put_resp.status_code != 200:
        print("Response code not 200")
        return False
    if (put_resp.text != """{"name":"Aoba","score":123}"""
            or get_resp.text != """{"name":"Aoba","score":123}"""):
        print("Result not correct")
        return False
    return True


def test17():
    """
    Test 17: API PUT survives reopen with automatic commits enabled or disabled.
    :return:
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        for auto_commit in (True, False):
            replay_path = str(Path(temp_dir) / f"api-{auto_commit}.log")
            jdb = JackDB(replay_path, auto_commit=auto_commit)
            app = serve_routes('Test', jdb)
            expected = {'text': 'hello', 'object': {'nested': [1, True, None]}}
            with TestClient(app) as client:
                for key, value in expected.items():
                    response = client.put(f'/Test/put/{key}', json={'value': value})
                    if response.status_code != 200 or response.json() != value:
                        print(f"PUT failed with auto_commit={auto_commit}: {response.text}")
                        return False
                    # Reopen before shutdown: the response must imply persistence.
                    reopened = JackDB(replay_path)
                    if reopened.do_operation({'op': 'get', 'k': key}) != value:
                        print(f"PUT did not persist with auto_commit={auto_commit}")
                        return False
    return True


def test18():
    """
    Test 18: API Set Test.
    :return:
    """
    init_test()
    jdb = JackDB('./tests/test.txt')
    app = serve_routes('Test', jdb)

    client = TestClient(app)
    input_data = {"field": "score", "value": 123}
    put_resp = client.put('Test/set/user:1', json=input_data)

    reopened = JackDB('./tests/test.txt')

    if put_resp.status_code != 200:
        print("Response code not 200")
        return False
    if (put_resp.text != """{"name":"Aoba","score":123}"""
            or reopened.do_get("user:1") != {"name": "Aoba", "score": 123}):
        print("Result not correct")
        return False
    return True


def test19():
    """
    Test 19: API Del Test.
    :return:
    """
    init_test()
    jdb = JackDB('./tests/test.txt')

    app = serve_routes('Test', jdb)
    client = TestClient(app)
    input_data = {"field": "score", "value": 123}
    del_resp = client.delete('Test/del/user:1', params=input_data)

    reopened = JackDB('./tests/test.txt')

    if "user:1" in reopened:
        print("user:1 found after reopen.")
        return False

    if del_resp.status_code != 200:
        print("Response code not 200")
        return False

    if del_resp.json() != {"message": "Item successfully deleted.", "id": "user:1"}:
        print("Result not correct")
        return False
    return True


def test20():
    """
    Test 20: Commit Fsync error
    :return:
    """
    init_test()
    jdb = JackDB('./tests/test.txt', auto_commit=False)
    jdb.do_operation(json.dumps(test_items.TEST_PUT_DATA2))

    with open(jdb.replay_path, "a+b", buffering=0) as replay_file:
        original_file_size = os.fstat(replay_file.fileno()).st_size

    # Patch fsync to throw an error
    with patch("jackdb.core.os.fsync", side_effect=[OSError("Thrown error"), None]) as p:
        try:
            jdb.commit()
        except OSError:
            pass
        else:
            print("OSError not thrown.")
            return False
        if p.call_count != 2:
            print("There should have been 2 calls to os.fsync.")
            return False

    with open(jdb.replay_path, "a+b", buffering=0) as replay_file:
        reopened_file_size = os.fstat(replay_file.fileno()).st_size

    # reopened file should have rolled back from the errors.
    if reopened_file_size != original_file_size:
        print("Original File was not restored properly.")
        return False

    jdb.commit()

    with open(jdb.replay_path, "a+b", buffering=0) as replay_file:
        reopened_file_size = os.fstat(replay_file.fileno()).st_size

    new_data_in_bytes = len((json.dumps(test_items.TEST_PUT_DATA2) + "\n").encode('utf-8'))

    # We have successfully commited and made sure all the data is now written
    if reopened_file_size != (original_file_size + new_data_in_bytes):
        print("New records not properly commited.")
        return False

    with JackDB('./tests/test.txt', auto_commit=False) as reopened:
        if reopened.do_get("user:3") != test_items.TEST_PUT_DATA2['v']:
            print("Bad record retrieved form user:3.")
            return False

    return True


def test21():
    """
    Test 21: A rejected SET does not block the next commit.
    :return:
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        replay_path = str(Path(temp_dir) / "db.log")
        jdb = JackDB(replay_path, auto_commit=False)

        jdb.do_operation({"op": "set", "k": "missing", "f": "field", "v": 1})
        results = jdb.commit()
        if len(results) != 1 or not isinstance(results[0].error, JdbException):
            print("SET on a missing key should have been rejected.")
            return False

        try:
            jdb.do_operation({"op": "put", "k": "valid", "v": 2})
            jdb.commit()
        except JdbException as exc:
            print(f"The rejected SET blocked the next PUT: {exc}")
            return False

        reopened = JackDB(replay_path)
        if reopened.do_get("valid") != 2:
            print("PUT after rejected SET did not persist.")
            return False
    return True


def test22():
    """
    Test 22: A stale SET is rejected after another writer commits DEL.
    :return:
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        replay_path = str(Path(temp_dir) / "db.log")
        writer = JackDB(replay_path, auto_commit=False)
        writer.do_operation({"op": "put", "k": "key", "v": {"field": 0}})
        writer.commit()
        stale_writer = JackDB(replay_path, auto_commit=False)
        writer.do_operation({"op": "del", "k": "key"})
        writer.commit()

        stale_writer.do_operation({"op": "set", "k": "key", "f": "field", "v": 1})
        results = stale_writer.commit()
        try:
            reopened = JackDB(replay_path)
        except JdbException as exc:
            print(f"The stale SET made the log unreplayable: {exc}")
            return False

        if len(results) != 1 or not isinstance(results[0].error, JdbException):
            print("Stale SET was not rejected.")
            return False
        if reopened.do_get("key") is not None:
            print("Deleted key is present after reopening.")
            return False
    return True


def test23():
    """
    Test 23: A queued PUT preserves the original operation.
    :return:
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        replay_path = str(Path(temp_dir) / "db.log")
        jdb = JackDB(replay_path, auto_commit=False)
        operation = {"op": "put", "k": "original", "v": {"score": 1}}
        jdb.do_operation(operation)
        operation["k"] = "edited"
        operation["v"]["score"] = 2
        jdb.commit()

        reopened = JackDB(replay_path)
        expected = {"score": 1}
        if jdb.do_get("original") != expected or jdb.do_get("edited") is not None:
            print("Editing the queued PUT changed the live database.")
            return False
        if reopened.do_get("original") != expected or reopened.do_get("edited") is not None:
            print("Editing the queued PUT changed the replayed database.")
            return False
    return True

def test24():
    """Test 24: Skip complete bad journal records and preserve the file."""
    first = b'{"op":"put","k":"key1","v":{"score":1}}\n'
    last = b'{"op":"put","k":"key2","v":{"score":2}}\n'
    cases = {
        "invalid interior records": first + b'{"op":"bad_op"}\nbad_line\n\n' + last,
        "interior list key": first + b'{"op":"put","k":["key3"],"v":3}\n' + last,
        "interior list key2": first + b'{"op":"put","k":[],"v":3}\n' + last,
        "complete bad final record": first + last + b'{"op":"bad_op"}\n',
    }
    expected = {"key1": {"score": 1}, "key2": {"score": 2}}
    passed = True

    with tempfile.TemporaryDirectory() as temp_dir:
        replay_path = Path(temp_dir) / "db.log"
        for name, original in cases.items():
            replay_path.write_bytes(original)
            for attempt in range(1, 3):
                try:
                    db = JackDB(str(replay_path))
                except (JdbException, TypeError) as exc:
                    print(f"{name}: open {attempt} raised {type(exc).__name__}: {exc}")
                    passed = False
                    break

                if {key: db.do_get(key) for key in db} != expected:
                    print(f"{name}: unexpected values on open {attempt}.")
                    passed = False
                if replay_path.read_bytes() != original:
                    print(f"{name}: journal bytes changed on open {attempt}.")
                    passed = False

    return passed


def run_tests():
    """Runs the tests."""
    passed = 0
    failed = 0

    functions = {'test1': test1(),
                 'test2': test2(),
                 'test3': test3(),
                 'test4': test4(),
                 'test5': test5(),
                 'test6': test6(),
                 'test7': test7(),
                 'test8': test8(),
                 'test9': test9(),
                 'test10': test10(),
                 'test11': test11(),
                 'test12': test12(),
                 'test13': test13(),
                 'test14': test14(),
                 'test15': test15(),
                 'test16': test16(),
                 'test17': test17(),
                 'test18': test18(),
                 'test19': test19(),
                 'test20': test20(),
                 'test21': test21(),
                 'test22': test22(),
                 'test23': test23(),
                 'test24': test24()
                 }

    failed_tests = []

    for function_name, did_pass in functions.items():

        if did_pass:
            passed += 1
        else:
            failed += 1
            failed_tests.append(function_name)
        teardown_test()

    print("Passed: ", passed, "\nFailed: ", failed)
    if len(failed_tests) == 0:
        print("No tests failed")
    else:
        print(f"Failed : {failed_tests}")


if __name__ == "__main__":
    run_tests()
