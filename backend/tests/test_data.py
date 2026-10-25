import gzip
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from app.services.dataset_service import Dataset, Registry, sha256

spec = importlib.util.spec_from_file_location('builder', Path(__file__).resolve().parents[1] / 'scripts/build_dataset.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.mark.parametrize('damage', ['hash', 'duplicate', 'order', 'dtype', 'nan', 'zero', 'diagnostic', 'transform', 'source', 'parameters'])
def test_corruption_rejected(dataset_folder, damage):
    meta_path = dataset_folder / 'metadata.json'
    meta = json.loads(meta_path.read_text('utf-8'))
    if damage in {'hash', 'duplicate', 'order'}:
        path = dataset_folder / 'points.json'
        payload = json.loads(path.read_text('utf-8'))
        if damage == 'duplicate': payload['points'][1]['id'] = 0
        elif damage == 'order':
            payload['points'][0]['word'], payload['points'][1]['word'] = payload['points'][1]['word'], payload['points'][0]['word']
        else: payload['points'][0]['word'] = 'tampered'
        path.write_text(json.dumps(payload), 'utf-8')
        if damage != 'hash': meta['checksums']['points.json'] = sha256(path)
    elif damage in {'dtype', 'nan', 'zero'}:
        path = dataset_folder / 'vectors.npy'
        x = np.load(path)
        if damage == 'dtype': x = x.astype('float64')
        elif damage == 'nan': x[0, 0] = np.nan
        else: x[0] = 0
        np.save(path, x)
        meta['checksums']['vectors.npy'] = sha256(path)
    elif damage == 'diagnostic': meta['diagnostics']['trustworthiness']['pca']['input_metric'] = 'euclidean'
    elif damage == 'transform': meta['display_transforms']['pca']['scale'] = -1
    elif damage == 'source': del meta['checksums']['source']
    else: meta['projection_params']['umap']['metric'] = 'euclidean'
    meta_path.write_text(json.dumps(meta), 'utf-8')
    registry = Registry(dataset_folder.parent)
    assert not registry.datasets
    assert dataset_folder.name in registry.failures


def test_uniform_scale_preserves_distance_ratios():
    y = np.array([[10, 2, -3], [0, 4, 9], [-8, 0, 3]], dtype=float)
    result, transform = builder.display_transform(y)
    np.testing.assert_allclose(result.mean(axis=0), 0, atol=1e-12)
    assert np.linalg.norm(result, axis=1).max() == pytest.approx(1)
    for i, j in [(0, 1), (1, 2)]:
        assert np.linalg.norm(result[i] - result[j]) == pytest.approx(np.linalg.norm(y[i] - y[j]) * transform['scale'])


@pytest.mark.parametrize('compressed', [True, False])
def test_stream_binary_extract_and_oov(tmp_path, compressed):
    path = tmp_path / ('test.bin.gz' if compressed else 'test.bin')
    x = np.arange(900, dtype='<f4').reshape(3, 300) + 1
    writer = gzip.open if compressed else open
    with writer(path, 'wb') as f:
        f.write(b'3 300\n')
        for word, vector in zip(['apple', 'New_York', 'car'], x):
            f.write(word.encode() + b' ' + vector.tobytes() + b'\n')
    np.testing.assert_array_equal(builder.extract_binary(path, ['car', 'apple']), x[[2, 0]])
    with pytest.raises(ValueError, match='OOV: missing'):
        builder.extract_binary(path, ['missing'])


def test_seed_count_and_content():
    words, report = builder.read_words(Path(__file__).resolve().parents[1] / 'data/seed_words.txt')
    assert len(words) == 1000 and not report['duplicates']
    assert {'king', 'woman', 'man', 'queen', 'apple', 'orange', 'car'} <= set(words)


def test_real_projection_build_reproducibility_and_no_overwrite(tmp_path):
    words = [f'test_{i}' for i in range(12)]
    x = builder.synthetic_vectors(words, dimensions=5)
    kwargs = dict(synthetic=True, model='test-random', source_url='local:test', license_note='project-generated',
                  source_hash='a' * 64, seed_hash='b' * 64)
    first, second = tmp_path / 'synthetic-first', tmp_path / 'synthetic-second'
    builder.write_dataset(first, words, x, report={}, **kwargs)
    builder.write_dataset(second, words, x, report={}, **kwargs)
    a, b = Dataset(first), Dataset(second)
    for algorithm in ('pca', 'umap'):
        np.testing.assert_allclose([p['positions'][algorithm] for p in a.points], [p['positions'][algorithm] for p in b.points], atol=1e-5, rtol=1e-5)
        assert a.metadata['diagnostics']['trustworthiness'][algorithm]['n_neighbors'] == 5
    before = sha256(first / 'vectors.npy')
    with pytest.raises(ValueError, match='already exists'):
        builder.write_dataset(first, words, x, report={}, **kwargs)
    assert sha256(first / 'vectors.npy') == before

