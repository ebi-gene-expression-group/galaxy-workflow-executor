import os
import json

from wfexecutor import ExecutionState, safe_download_path

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


def test_save_state_writes_json(tmp_path):
    state_path = tmp_path / "exec_state.json"
    es = ExecutionState.start(str(state_path))
    es.datamap = {'key': 'value'}
    es.params = {'step': {'parameter': 'setting'}}
    es.save_state()

    with open(str(state_path)) as f:
        data = json.load(f)

    assert data['datamap'] == {'key': 'value'}
    assert data['params'] == {'step': {'parameter': 'setting'}}
    assert data['results'] is None


def test_safe_download_path_allows_plain_filename(tmp_path):
    assert safe_download_path(str(tmp_path), "results.tsv") == str(tmp_path / "results.tsv")


def test_safe_download_path_rejects_traversal(tmp_path):
    try:
        safe_download_path(str(tmp_path), "../results.tsv")
        assert False
    except ValueError:
        pass


def test_safe_download_path_rejects_absolute_path(tmp_path):
    try:
        safe_download_path(str(tmp_path), "/tmp/results.tsv")
        assert False
    except ValueError:
        pass
