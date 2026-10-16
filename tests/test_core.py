"""Driver for the tests."""
import tempfile
import json
import shutil
from pathlib import Path
import test_items
from jackdb import JackDB
from jackdb.exceptions import JdbException


def init_test():
    """
    Initialize the test text file
    :return:
    """
    shutil.copy('./tests/test_file1.txt', './tests/test.txt')


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
                 'test8': test8()
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
