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
