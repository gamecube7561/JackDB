"""Contains items used by the tests."""
TEST_PUT_DATA = {
    'op': 'put',
    'k': 'user:1',
    'v': {
        'name': 'Aoba',
        'score': 10
    }
}

TEST_PUT_OUTPUT = {
    'user:1': {
        'name': 'Aoba',
        'score': 10
    },
    'cfg': [1, 2, 3]}

TEST_PUT_DATA2 = {
    'op': 'put',
    'k': 'user:3',
    'v': {
        'name': 'Aoba',
        'score': 10
    }
}

TEST_PUT_DATA3 = {
    'op': 'put',
    'k': 'user:3',
    'v': {
        'name': 'Aoba',
        'score': 20
    }
}

TEST_SET_DATA1 = {
    'op': 'set',
    'k': 'user:3',
    'f': 'state',
    'v': 'NY'
}

TEST_GET_MANY1 = {
    'op': 'get_many',
    'k': ['user:1', 'user:3']
}

TEST_PUT_OUTPUT2 = {
    'user:1': {
        'name': 'Aoba',
        'score': 10
    },
    'user:3': {
        'name': 'Aoba',
        'score': 20
    },
    'cfg': [1, 2, 3]}

TEST_PUT_OUTPUT3 = {
    'user:1': {
        'name': 'Aoba',
        'score': 10
    },
    'user:3': {
        'name': 'Aoba',
        'score': 20,
        'state': 'NY'
    },
    'cfg': [1, 2, 3]}

TEST_BAD_OPERATION ={
    'op': 'evil_operation'
}