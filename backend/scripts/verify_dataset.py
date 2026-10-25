"""Validate a built dataset and report factual math checks; optionally compare a rebuild."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.dataset_service import Dataset
from app.services.embedding_service import analogy, neighbors, similarity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--compare', type=Path)
    args = parser.parse_args()
    ds = Dataset(args.dataset.resolve())
    matrix = similarity(ds, ['apple', 'orange', 'car'])
    values = np.asarray(matrix['matrix'])
    np.testing.assert_allclose(values, values.T, atol=1e-6)
    np.testing.assert_allclose(values.diagonal(), 1, atol=1e-6)
    nn = neighbors(ds, 'apple', 10)
    assert all(w['word'] != 'apple' for w in nn['results'])
    result = {'dataset_id': ds.metadata['dataset_id'], 'data_kind': ds.metadata['data_kind'],
              'point_count': len(ds.words), 'dimensions': ds.vectors.shape[1], 'comparison': matrix,
              'apple_neighbors': nn, 'king_minus_man_plus_woman': analogy(ds, ['king', 'woman'], ['man'], 10, True),
              'diagnostics': ds.metadata['diagnostics']}
    if args.compare:
        other = Dataset(args.compare.resolve())
        assert ds.words == other.words
        np.testing.assert_array_equal(ds.vectors, other.vectors)
        differences = {}
        for algorithm in ('pca', 'umap'):
            # Compare original algorithm outputs, undoing uniform display transforms.
            outputs = []
            for dataset in (ds, other):
                transform = dataset.metadata['display_transforms'][algorithm]
                outputs.append(np.array([p['positions'][algorithm] for p in dataset.points]) / transform['scale'] + transform['center'])
            np.testing.assert_allclose(*outputs, atol=1e-5, rtol=1e-5)
            differences[algorithm] = {'max_coordinate_difference': float(np.abs(outputs[0] - outputs[1]).max()),
                'trustworthiness_difference': abs(ds.metadata['diagnostics']['trustworthiness'][algorithm]['value'] - other.metadata['diagnostics']['trustworthiness'][algorithm]['value'])}
        result['reproducibility'] = differences
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
