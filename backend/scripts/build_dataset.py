"""Explicit offline build: real local Word2Vec or visibly labelled synthetic data."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import sys
import tempfile
import time
import ctypes
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.dataset_service import Dataset, ID_PATTERN, sha256, token_hash


def read_words(path: Path):
    raw = [w.strip() for w in path.read_text("utf-8").splitlines() if w.strip()]
    words = list(dict.fromkeys(raw))
    duplicates = sorted({w for w in raw if raw.count(w) > 1})
    if any(len(w) > 128 for w in words):
        raise ValueError("Token exceeds 128 characters")
    return words, {"input_count": len(raw), "unique_count": len(words), "duplicates": duplicates}


def extract_binary(path: Path, words: list[str]) -> np.ndarray:
    """Scan word2vec binary records without loading the source vocabulary into RAM."""
    found = {}
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        total, dims = map(int, stream.readline().split())
        if total <= 0 or dims != 300:
            raise ValueError("Expected a 300-dimensional word2vec binary source")
        wanted = set(words)
        for _ in range(total):
            token = bytearray()
            while True:
                char = stream.read(1)
                if not char:
                    raise ValueError("Truncated word2vec token")
                if char == b" ":
                    break
                if char == b"\n" and not token:
                    continue
                token.extend(char)
            data = stream.read(dims * 4)
            if len(data) != dims * 4:
                raise ValueError("Truncated word2vec vector")
            word = token.decode("utf-8", errors="replace")
            if word in wanted:
                found[word] = np.frombuffer(data, dtype="<f4").copy()
    missing = [w for w in words if w not in found]
    if missing:
        raise ValueError("OOV: " + ", ".join(missing))
    return np.asarray([found[w] for w in words], dtype="<f4")


def synthetic_vectors(words: list[str], dimensions=300):
    # Arbitrary random vectors, deliberately NOT a pretrained semantic model.
    rng = np.random.default_rng(42)
    return (rng.normal(size=(len(words), dimensions)) * rng.uniform(0.5, 2, (len(words), 1))).astype("<f4")


def display_transform(y):
    center = y.mean(axis=0)
    radius = np.linalg.norm(y - center, axis=1).max()
    if not np.isfinite(radius) or radius <= 1e-12:
        raise ValueError("Degenerate projection")
    scale = float(1 / radius)
    return (y - center) * scale, {"method": "center_max_radius", "center": center.tolist(), "scale": scale}


def peak_memory_bytes():
    if sys.platform == 'win32':
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                    'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        get_process = ctypes.windll.kernel32.GetCurrentProcess
        get_process.restype = wintypes.HANDLE
        get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        if get_memory(get_process(), ctypes.byref(counters), counters.cb):
            return counters.PeakWorkingSetSize
        return None
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(peak if sys.platform == 'darwin' else peak * 1024)
    except (ImportError, OSError):
        return None


def write_dataset(output: Path, words: list[str], vectors: np.ndarray, *, synthetic: bool,
                  model: str, source_url: str, license_note: str, source_hash: str,
                  seed_hash: str, report: dict, source_format="generated", extract_mode="synthetic"):
    start = time.perf_counter()
    from sklearn.decomposition import PCA
    from sklearn.manifold import trustworthiness
    from umap import UMAP

    if output.exists():
        raise ValueError("Output already exists; choose a new dataset version")
    if not ID_PATTERN.fullmatch(output.name):
        raise ValueError("Invalid dataset ID")
    x = np.asarray(vectors, dtype="<f4")
    if x.ndim != 2 or len(words) != len(x) or len(set(words)) != len(words) or min(x.shape) < 3:
        raise ValueError("Invalid vector shape or vocabulary")
    if not synthetic and x.shape != (1000, 300):
        raise ValueError("Pretrained MVP requires exactly 1000 x 300")
    xf = x.astype(np.float64)
    if not np.isfinite(xf).all() or np.any(np.linalg.norm(xf, axis=1) == 0):
        raise ValueError("Nonfinite or zero vectors")
    pca = PCA(n_components=3, svd_solver="full", whiten=False)
    # Random initialization is necessary for tiny test fixtures; record the override.
    umap = UMAP(n_components=3, n_neighbors=min(15, len(x) - 1), min_dist=0.1, metric="cosine",
                output_metric="euclidean", init="spectral" if len(x) > 4 else "random", random_state=42, n_jobs=1)
    layouts = {"pca": pca.fit_transform(xf), "umap": umap.fit_transform(xf).astype(np.float64)}
    k = min(10, (len(x) - 1) // 2)
    diagnostics = {"pca_explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
                   "pca_explained_variance_total": float(pca.explained_variance_ratio_.sum()),
                   "trustworthiness": {a: {"value": float(trustworthiness(xf, y, n_neighbors=k, metric="cosine")),
                       "n_neighbors": k, "input_metric": "cosine", "output_metric": "euclidean", "sample_count": len(x)}
                       for a, y in layouts.items()}}
    transformed = {a: display_transform(y) for a, y in layouts.items()}
    points = [{"id": i, "word": w, "positions": {a: transformed[a][0][i].tolist() for a in layouts}} for i, w in enumerate(words)]
    build = {"created_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
             "platform": platform.platform(), "dependencies": {p: importlib.metadata.version(p) for p in
                 ("numpy", "scipy", "scikit-learn", "umap-learn", "numba", "gensim")},
             "threads": {"umap_n_jobs": 1, "NUMBA_NUM_THREADS": os.environ.get("NUMBA_NUM_THREADS"),
                         "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS")},
             "script_sha256": sha256(Path(__file__)), "source_format": source_format, "extract_mode": extract_mode}
    meta = {"schema_version": 1, "dataset_id": output.name, "data_kind": "synthetic" if synthetic else "pretrained",
            "model_name": model, "source_url": source_url, "license_note": license_note,
            "embedding_dimensions": x.shape[1], "point_count": len(x), "algorithms": ["pca", "umap"], "random_seed": 42,
            "vector_dtype": "float32", "vector_normalization": "none", "id_policy": "seed_order_row_index",
            "projection_params": {"pca": {**pca.get_params(), "input_normalization": "none"},
                                  "umap": {**umap.get_params(), "input_normalization": "none"}},
            "display_transforms": {a: transformed[a][1] for a in layouts}, "diagnostics": diagnostics,
            "numeric_policy": {"target_relative_epsilon": 1e-12, "math_atol": 1e-6, "math_rtol": 1e-6,
                               "projection_atol": 1e-5, "projection_rtol": 1e-5},
            "build": build, "checksums": {"source": source_hash, "seed_file": seed_hash, "tokens": token_hash(words)}}
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".build-", dir=output.parent))
    folder = staging / output.name
    folder.mkdir()
    try:
        np.save(folder / "vectors.npy", x, allow_pickle=False)
        (folder / "points.json").write_text(json.dumps({"dataset_id": output.name, "points": points}, ensure_ascii=False, allow_nan=False), "utf-8")
        meta["checksums"].update({name: sha256(folder / name) for name in ("points.json", "vectors.npy")})
        (folder / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False, allow_nan=False), "utf-8")
        Dataset(folder)
        report.update({"valid_count": len(words), "oov": [], "projection_seconds": round(time.perf_counter() - start, 3),
                       "source_sha256": source_hash, "peak_memory_bytes": peak_memory_bytes(), "peak_memory_note": "Process peak resident/working-set bytes; null means unavailable"})
        report['total_seconds'] = round(report.get('preparation_seconds', 0) + time.perf_counter() - start, 3)
        (folder / "build-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), "utf-8")
        folder.rename(output)
    finally:
        # Only our own freshly created temporary directory is removed.
        if staging.resolve().parent != output.parent.resolve() or not staging.name.startswith('.build-'):
            raise RuntimeError('Unexpected staging path; refusing cleanup')
        shutil.rmtree(staging)
    return meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-file", type=Path, default=Path(__file__).resolve().parents[1] / "data/seed_words.txt")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--model", default="word2vec-google-news-300")
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--extract-mode", choices=["stream", "gensim"], default="stream")
    parser.add_argument("--source-url", default="https://code.google.com/archive/p/word2vec/")
    parser.add_argument("--license-note", default="")
    args = parser.parse_args()
    started = time.perf_counter()
    report = {}
    try:
        words, report = read_words(args.seed_file)
        if len(words) != 1000:
            raise ValueError(f"Seed list must contain exactly 1000 unique words; got {len(words)}")
        if args.synthetic:
            if not args.output.name.startswith("synthetic-"):
                raise ValueError("Synthetic dataset ID must begin with synthetic-")
            x = synthetic_vectors(words)
            model, url, license_note = "synthetic-random-300", "local:synthetic-generator", "Project-generated random test vectors; not pretrained semantics."
            source_hash = sha256(Path(__file__))
            source_format = "generated"
        else:
            if not args.license_note:
                raise ValueError("Provide --license-note describing the verified source terms and intended usage")
            path = args.model_path
            if path is None:
                import gensim.downloader as api
                path = Path(api.BASE_DIR) / args.model / f"{args.model}.gz"
            if not path.is_file():
                raise ValueError("Model missing. Explicitly download using: python scripts/download_model.py ; or pass --model-path")
            print(f"Reading local source: {path.resolve()}", flush=True)
            source_hash = sha256(path)
            source_format = "word2vec-binary-gzip" if path.suffix == ".gz" else "word2vec-binary"
            if args.extract_mode == "stream":
                x = extract_binary(path, words)
            else:
                from gensim.models import KeyedVectors
                model_vectors = KeyedVectors.load_word2vec_format(str(path), binary=True)
                missing = [w for w in words if w not in model_vectors]
                if missing:
                    raise ValueError("OOV: " + ", ".join(missing))
                x = np.asarray([model_vectors[w] for w in words], dtype="<f4")
            model, url, license_note = args.model, args.source_url, args.license_note
        report['preparation_seconds'] = round(time.perf_counter() - started, 3)
        meta = write_dataset(args.output.resolve(), words, x, synthetic=args.synthetic, model=model, source_url=url,
                             license_note=license_note, source_hash=source_hash, seed_hash=sha256(args.seed_file),
                             report=report, source_format=source_format, extract_mode="synthetic" if args.synthetic else args.extract_mode)
        print(json.dumps({"output": str(args.output.resolve()), "dataset_id": meta["dataset_id"],
                          "seconds": round(time.perf_counter() - started, 2), "diagnostics": meta["diagnostics"]}, indent=2))
    except Exception as exc:
        report.update({"error": str(exc), "seconds": round(time.perf_counter() - started, 2)})
        if str(exc).startswith("OOV: "):
            report["oov"] = str(exc)[5:].split(", ")
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

