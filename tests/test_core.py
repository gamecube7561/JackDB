from jackdb.main import JackDB
import test_items
import tempfile
import json


def init_test():
    import shutil as sh
    sh.copy('./tests/test_file1.txt', './tests/test.txt')


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
    jdb.replay_file.close()

    # Acceptance: flushed record survives reopen (log-before-apply consistency)
    reopened = JackDB('./tests/test.txt')
    expected = dict(test_items.TEST_PUT_OUTPUT)
    expected['user:3'] = test_items.TEST_PUT_DATA2['v']
    reopened.replay_file.close()

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
    jdb.replay_file.close()

    reopened = JackDB('./tests/test.txt')
    expected = dict(test_items.TEST_PUT_OUTPUT2)
    reopened.replay_file.close()
    if reopened.data_dict != expected:
        print(f"Test 4 \nexpected: {expected}\ngot: {reopened.data_dict}")
        return False
    return True


def run_tests():
    passed = 0
    failed = 0

    functions = {'test1': test1(),
                 'test2': test2(),
                 'test3': test3(),
                 'test4': test4(),
                 }

    failed_tests = []

    for fun in functions:

        if functions[fun]:
            passed += 1
        else:
            failed += 1
            failed_tests.append(fun)

    print("Passed: ", passed, "\nFailed: ", failed)
    if len(failed_tests) == 0:
        print("No tests failed")
    else:
        print(f"Failed : {failed_tests}")


if __name__ == "__main__":
    run_tests()
