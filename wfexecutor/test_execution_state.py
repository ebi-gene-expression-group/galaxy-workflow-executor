import os

from wfexecutor import ExecutionState

test_state = "test.bin"

def test_create_new_es():
    if os.path.isfile(test_state):
        os.remove(test_state)
    es = ExecutionState.start(test_state)
    assert es.datamap is None
    es.datamap = {'key': 'value'}
    es.save_state()

def test_reload_es():
    es = ExecutionState.start(test_state)
    assert 'key' in es.datamap
    assert es.datamap['key'] == 'value'
