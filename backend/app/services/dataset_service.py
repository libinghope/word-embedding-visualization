"""Validated, immutable datasets; no model download or projection at request time."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
from ..models.schemas import MetadataResponse

ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def token_hash(words: list[str]) -> str:
    return hashlib.sha256("".join(w + "\n" for w in words).encode("utf-8")).hexdigest()


class Dataset:
    def __init__(self, folder: Path):
        self.metadata = m = json.loads((folder / "metadata.json").read_text("utf-8"))
        MetadataResponse.model_validate(m)
        required = {"schema_version", "dataset_id", "data_kind", "model_name", "source_url", "license_note",
                    "embedding_dimensions", "point_count", "vector_dtype", "vector_normalization", "id_policy",
                    "projection_params", "display_transforms", "diagnostics", "numeric_policy", "build", "checksums"}
        if not required <= m.keys() or m["schema_version"] != 1:
            raise ValueError("Incomplete or unsupported metadata")
        if not ID_PATTERN.fullmatch(m["dataset_id"]) or folder.name != m["dataset_id"]:
            raise ValueError("Dataset ID mismatch")
        if m["data_kind"] not in {"synthetic", "pretrained"}:
            raise ValueError("Invalid data kind")
        if m["vector_normalization"] != "none" or m["vector_dtype"] != "float32" or m["id_policy"] != "seed_order_row_index":
            raise ValueError("Unsupported vector or ID policy")
        for key in ('source', 'seed_file', 'tokens', 'points.json', 'vectors.npy'):
            digest = m['checksums'].get(key, '')
            if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
                raise ValueError('Missing or invalid provenance checksum')
        for key in ('model_name', 'source_url', 'license_note'):
            if not isinstance(m[key], str) or not m[key].strip():
                raise ValueError('Missing source documentation')
        build_fields = {'created_at', 'python', 'platform', 'dependencies', 'threads', 'script_sha256', 'source_format', 'extract_mode'}
        if not build_fields <= m['build'].keys():
            raise ValueError('Incomplete build provenance')
        if not re.fullmatch(r'[0-9a-f]{64}', m['build']['script_sha256']):
            raise ValueError('Invalid script checksum')
        for filename in ("points.json", "vectors.npy"):
            if sha256(folder / filename) != m["checksums"].get(filename):
                raise ValueError(f"Checksum mismatch: {filename}")
        payload = json.loads((folder / "points.json").read_text("utf-8"))
        self.points = payload["points"]
        if payload["dataset_id"] != m["dataset_id"]:
            raise ValueError("Points dataset ID mismatch")
        n, d = m["point_count"], m["embedding_dimensions"]
        if not isinstance(n, int) or not isinstance(d, int) or n < 3 or d < 3:
            raise ValueError("Invalid dimensions")
        if m["data_kind"] == "pretrained" and (n, d) != (1000, 300):
            raise ValueError("MVP pretrained datasets require 1000 x 300")
        if len(self.points) != n or [p["id"] for p in self.points] != list(range(n)):
            raise ValueError("Invalid point count or IDs")
        self.words = [p["word"] for p in self.points]
        if any(not isinstance(w, str) or not w or w != w.strip() or len(w) > 128 for w in self.words):
            raise ValueError("Invalid token")
        if len(set(self.words)) != n or token_hash(self.words) != m["checksums"].get("tokens"):
            raise ValueError("Duplicate or reordered tokens")
        raw = np.load(folder / "vectors.npy", allow_pickle=False)
        if raw.shape != (n, d) or raw.dtype.str != "<f4" or not np.isfinite(raw).all():
            raise ValueError("Invalid vector array")
        self.vectors = raw.astype(np.float64)
        norms = np.linalg.norm(self.vectors, axis=1)
        if np.any(norms == 0):
            raise ValueError("Zero vector")
        self.units = self.vectors / norms[:, None]
        self.vectors.flags.writeable = False
        self.units.flags.writeable = False
        self.index = {word: i for i, word in enumerate(self.words)}
        for algorithm in ("pca", "umap"):
            xyz = np.asarray([p["positions"][algorithm] for p in self.points], dtype=float)
            transform = m["display_transforms"][algorithm]
            center = np.asarray(transform["center"], dtype=float)
            scale = transform["scale"]
            if xyz.shape != (n, 3) or not np.isfinite(xyz).all() or center.shape != (3,) or not np.isfinite(center).all():
                raise ValueError("Invalid projection")
            if transform["method"] != "center_max_radius" or not np.isfinite(scale) or scale <= 0:
                raise ValueError("Invalid display transform")
            diag = m["diagnostics"]["trustworthiness"][algorithm]
            if not 0 <= diag["value"] <= 1 or diag["n_neighbors"] != min(10, (n - 1) // 2):
                raise ValueError("Invalid diagnostic")
            if diag["input_metric"] != "cosine" or diag["output_metric"] != "euclidean" or diag["sample_count"] != n:
                raise ValueError("Invalid diagnostic metrics")
            params = m["projection_params"][algorithm]
            if params["n_components"] != 3 or params["input_normalization"] != "none":
                raise ValueError("Invalid projection parameters")
            if algorithm == 'pca' and (params.get('svd_solver') != 'full' or params.get('whiten') is not False):
                raise ValueError('Unsupported PCA parameters')
            if algorithm == 'umap':
                expected = {'metric': 'cosine', 'output_metric': 'euclidean', 'n_neighbors': min(15, n - 1),
                            'min_dist': .1, 'random_state': 42, 'n_jobs': 1, 'init': 'spectral' if n > 4 else 'random'}
                if any(params.get(key) != value for key, value in expected.items()):
                    raise ValueError('Unsupported UMAP parameters')
        ratios = np.asarray(m["diagnostics"]["pca_explained_variance_ratio"], dtype=float)
        if ratios.shape != (3,) or not np.isfinite(ratios).all() or np.any(ratios < 0) or ratios.sum() > 1 + 1e-6:
            raise ValueError("Invalid explained variance")
        if not np.isclose(ratios.sum(), m["diagnostics"]["pca_explained_variance_total"]):
            raise ValueError("Invalid cumulative variance")
        if m["numeric_policy"].get("target_relative_epsilon") != 1e-12:
            raise ValueError("Unsupported numeric policy")
        json.dumps(m, allow_nan=False)


class Registry:
    def __init__(self, root: Path):
        self.datasets: dict[str, Dataset] = {}
        self.failures: dict[str, str] = {}
        for folder in sorted(root.glob("*")):
            if not folder.is_dir() or folder.name.startswith("."):
                continue
            try:
                dataset = Dataset(folder)
                self.datasets[dataset.metadata["dataset_id"]] = dataset
            except Exception as exc:
                self.failures[folder.name] = str(exc)

