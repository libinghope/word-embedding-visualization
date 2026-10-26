from types import SimpleNamespace
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.services.dataset_service import Dataset
from app.services.embedding_service import bridges, DomainError


def test_scores_symmetry_ties_and_exclusion(dataset_folder):
    ds = Dataset(dataset_folder)
    result = bridges(ds, ['king'], ['woman'], 20, 0)
    assert [r['word'] for r in result['results']][:2] == ['apple', 'orange']
    assert result['results'][0]['bridge'] == pytest.approx(1 / np.sqrt(2))
    reverse = bridges(ds, ['woman'], ['king'], 20, 0)
    assert [r['id'] for r in result['results']] == [r['id'] for r in reverse['results']]
    for x, y in zip(result['results'], reverse['results']):
        assert x['sA'] == y['sB']
        assert x['bridge'] == y['bridge']
    assert not {'king', 'woman'} & {r['word'] for r in result['results']}
    assert bridges(ds, ['king'], ['woman'], 20, 0.99)['results'] == []
    assert bridges(ds, ['king', 'king'], ['king'], 20, 0)['shared_inputs'] == ['king']


def test_zero_domain_and_oov(dataset_folder):
    ds = SimpleNamespace(index={'a': 0, 'b': 1}, units=np.array([[1., 0], [-1., 0]]))
    with pytest.raises(DomainError) as exc:
        bridges(ds, ['a', 'b'], ['a'], 10, 0)
    assert exc.value.code == 'ZERO_DOMAIN_VECTOR'
    with pytest.raises(DomainError) as exc:
        bridges(Dataset(dataset_folder), ['unknown'], ['king'], 10, 0)
    assert exc.value.details['words'] == ['unknown']


def test_bridge_api_validation(dataset_folder):
    with TestClient(create_app(dataset_folder.parent)) as client:
        body = {'dataset_id': dataset_folder.name, 'a': ['king'], 'b': ['woman']}
        assert client.post('/api/v1/bridges', json=body).status_code == 200
        for change in [{'a': []}, {'a': ['king'] * 6}, {'threshold': -1}, {'threshold': 1.1}, {'k': 51}]:
            assert client.post('/api/v1/bridges', json={**body, **change}).status_code == 422
        assert client.post('/api/v1/bridges', json={**body, 'a': ['unknown']}).status_code == 404
