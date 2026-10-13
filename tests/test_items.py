TEST_PUT_DATA = {
    'op': 'put',
    'k': 'user1',
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
    'k': 'user3',
    'v': {
        'name': 'Aoba',
        'score': 10
    }
}
