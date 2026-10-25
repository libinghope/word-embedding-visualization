import json
from pathlib import Path

import numpy as np
import pytest

from app.services.dataset_service import sha256, token_hash


@pytest.fixture
def dataset_folder(tmp_path):
    """Tiny hand-calculated test fixture, never presented as a model or projection."""
    folder = tmp_path / "synthetic-test"
    folder.mkdir()
    words = ["king", "man", "woman", "queen", "apple", "orange", "car"]
    vectors = np.array([[4, 0, 0], [1, 0, 0], [0, 2, 0], [3, 2, 0], [1, 1, 0], [1, 1, 0], [0, 0, 1]], dtype="<f4")
    np.save(folder / "vectors.npy", vectors)
    points = [{"id": i, "word": w, "positions": {"pca": [i / 7, 0, 0], "umap": [0, i / 7, 0]}} for i, w in enumerate(words)]
    (folder / "points.json").write_text(json.dumps({"dataset_id": folder.name, "points": points}), "utf-8")
    meta = {"schema_version": 1, "dataset_id": folder.name, "data_kind": "synthetic", "model_name": "unit-test",
            "source_url": "local:test", "license_note": "hand-authored test fixture", "embedding_dimensions": 3,
            "point_count": 7, "vector_dtype": "float32", "vector_normalization": "none", "id_policy": "seed_order_row_index",
            "projection_params": {'pca': {'n_components': 3, 'input_normalization': 'none', 'svd_solver': 'full', 'whiten': False},
                                  'umap': {'n_components': 3, 'input_normalization': 'none', 'metric': 'cosine', 'output_metric': 'euclidean',
                                           'n_neighbors': 6, 'min_dist': .1, 'random_state': 42, 'n_jobs': 1, 'init': 'spectral'}},
            "display_transforms": {a: {"center": [0, 0, 0], "scale": 1, "method": "center_max_radius"} for a in ("pca", "umap")},
            "diagnostics": {"pca_explained_variance_ratio": [0.5, 0.3, 0.2], "pca_explained_variance_total": 1,
                            "trustworthiness": {a: {"value": 0.5, "n_neighbors": 3, "input_metric": "cosine", "output_metric": "euclidean", "sample_count": 7} for a in ("pca", "umap")}},
            "numeric_policy": {"target_relative_epsilon": 1e-12},
            "build": {'created_at': '2026-10-25T00:00:00+00:00', 'python': 'test', 'platform': 'test', 'dependencies': {},
                      'threads': {}, 'script_sha256': 'c' * 64, 'source_format': 'fixture', 'extract_mode': 'fixture'},
            "checksums": {'source': 'a' * 64, 'seed_file': 'b' * 64, "points.json": sha256(folder / "points.json"), "vectors.npy": sha256(folder / "vectors.npy"), "tokens": token_hash(words)}}
    (folder / "metadata.json").write_text(json.dumps(meta), "utf-8")
    return folder

