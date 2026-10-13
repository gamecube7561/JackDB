import shutil

from jackdb.main import JackDB
import test_items
import tempfile
import json


def init_test():
    import shutil as sh
    sh.copy('./tests/test_file1.txt', './tests/test.txt')

def test1():
    init_test()
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as temp_file:
        temp_text = json.dumps(test_items.TEST_PUT_DATA)
        temp_file.write(temp_text)
        temp_file.flush()
        jdb = JackDB(str(temp_file.name))
        return jdb.records[0] == test_items.TEST_PUT_DATA


def test2():
    init_test()
    jdb = JackDB('./tests/test.txt')
    return jdb.data_dict == test_items.TEST_PUT_OUTPUT

def test3():
    init_test()
    jdb = JackDB('./tests/test.txt')
    jdb.do_operation(json.dumps(test_items.TEST_PUT_DATA2))
    jdb.flush_logs()
    jdb.replay_file.close()

    # Acceptance: flushed record survives reopen (log-before-apply consistency)
    reopened = JackDB('./tests/test.txt')
    expected = dict(test_items.TEST_PUT_OUTPUT)
    expected['user3'] = test_items.TEST_PUT_DATA2['v']
    result = reopened.data_dict == expected
    reopened.replay_file.close()
    return result


def run_tests():
    passed = 0
    failed = 0

    functions = {'test1': test1(),
                 'test2': test2(),
                 'test3': test3()
                 }

    failed_tests = []

    for fun in functions:

        if functions[fun]:
            passed += 1
        else:
            failed += 1
            failed_tests.append(fun)

    print("passed: ", passed, " failed: ", failed)
    print(f"failed : {failed_tests}")

if __name__ == "__main__":
    run_tests()