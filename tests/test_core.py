from jackdb.main import JackDB
import test_items
import tempfile
import json



def test1():
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as temp_file:
        temp_text = json.dumps(test_items.TEST_PUT_DATA)
        temp_file.write(temp_text)
        temp_file.flush()
        jdb = JackDB(str(temp_file.name))
        jdb.replay_file.close()
        return jdb.records[0] == test_items.TEST_PUT_DATA


def test2():
    jdb = JackDB('./tests/test.txt.bak')
    jdb.replay_file.close()
    return jdb.data_dict == test_items.TEST_PUT_OUTPUT

def test3():
    jdb = JackDB('./tests/test.txt')
    jdb.do_operation(json.dumps(test_items.TEST_PUT_DATA2))
    # jdb.flush_logs()
    return


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