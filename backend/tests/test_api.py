import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(dataset_folder):
    with TestClient(create_app(dataset_folder.parent)) as client:
        yield client


def test_dataset_and_metadata(client):
    assert client.get('/api/v1/health').status_code == 200
    assert len(client.get('/api/v1/datasets').json()) == 1
    meta = client.get('/api/v1/datasets/synthetic-test/metadata').json()
    assert meta['diagnostics']['trustworthiness']['pca']['input_metric'] == 'cosine'
    assert len(client.get('/api/v1/datasets/synthetic-test/points').json()['points']) == 7


def test_search_normalization_and_case(client):
    base = '/api/v1/words/search'
    params = {'dataset_id': 'synthetic-test', 'q': '  man  '}
    assert [w['word'] for w in client.get(base, params=params).json()] == ['man', 'woman']
    assert client.get(base, params={**params, 'q': 'MAN'}).json() == []
    assert client.get(base, params={**params, 'q': ' '}).status_code == 422


@pytest.mark.parametrize('path,body,status,code', [
    ('similarity', {'words': ['king', ' king ']}, 422, 'VALIDATION_ERROR'),
    ('similarity', {'words': ['king', 'missing']}, 404, 'WORD_NOT_FOUND'),
    ('similarity', {'words': []}, 422, 'VALIDATION_ERROR'),
    ('similarity', {'words': ['king'] * 11}, 422, 'VALIDATION_ERROR'),
    ('analogy', {'positive': ['king'], 'negative': ['king']}, 400, 'ZERO_TARGET_VECTOR'),
    ('analogy', {'positive': ['king'], 'k': 51}, 422, 'VALIDATION_ERROR'),
    ('analogy', {'positive': ['king'] * 6, 'negative': ['woman'] * 5}, 422, 'VALIDATION_ERROR'),
    ('analogy', {'positive': ['king'], 'k': 1.5}, 422, 'VALIDATION_ERROR'),
])
def test_errors(client, path, body, status, code):
    response = client.post('/api/v1/' + path, json={'dataset_id': 'synthetic-test', **body})
    assert response.status_code == status
    assert response.json()['error']['code'] == code


def test_valid_math_and_bounds(client):
    response = client.post('/api/v1/analogy', json={'dataset_id': 'synthetic-test', 'positive': ['king', 'woman'], 'negative': ['man']})
    assert response.json()['results'][0]['word'] == 'queen'
    response = client.get('/api/v1/neighbors', params={'dataset_id': 'synthetic-test', 'word': 'king', 'k': 50})
    assert response.json()['candidate_scope'] == 'current_dataset'
    assert response.json()['returned_count'] == 6
    assert client.get('/api/v1/neighbors', params={'dataset_id': 'synthetic-test', 'word': 'king', 'k': 0}).status_code == 422
    assert client.get('/api/v1/datasets/unknown/metadata').status_code == 404
    assert client.get('/api/v1/datasets/INVALID/metadata').status_code == 422


def test_cors(client):
    path = '/api/v1/health'
    assert client.get(path, headers={'Origin': 'http://localhost:5173'}).headers['access-control-allow-origin'] == 'http://localhost:5173'
    assert 'access-control-allow-origin' not in client.get(path, headers={'Origin': 'https://untrusted.example'}).headers


def test_unavailable(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        response = client.get('/api/v1/health')
        assert response.status_code == 503
        assert response.json()['error']['code'] == 'DATASET_UNAVAILABLE'

