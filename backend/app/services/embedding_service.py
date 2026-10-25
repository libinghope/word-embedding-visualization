from __future__ import annotations

import numpy as np

from .dataset_service import Dataset


class DomainError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        self.status, self.code, self.message, self.details = status, code, message, details or {}


def ids_for(dataset: Dataset, words: list[str]) -> list[int]:
    missing = list(dict.fromkeys(w for w in words if w not in dataset.index))
    if missing:
        raise DomainError(404, "WORD_NOT_FOUND", "当前数据集未收录这些词。", {"words": missing})
    return [dataset.index[w] for w in words]


def space(dataset: Dataset) -> str:
    return f"original_embedding_{dataset.metadata['embedding_dimensions']}d"


def similarity(dataset: Dataset, words: list[str]) -> dict:
    units = dataset.units[ids_for(dataset, words)]
    return {"dataset_id": dataset.metadata["dataset_id"], "metric": "cosine", "space": space(dataset),
            "words": words, "matrix": np.clip(units @ units.T, -1, 1).tolist()}


def rank(dataset: Dataset, target: np.ndarray, excluded: set[int], k: int) -> dict:
    scores = dataset.units @ target
    candidates = np.array([i for i in range(len(dataset.words)) if i not in excluded], dtype=int)
    order = candidates[np.lexsort((candidates, -scores[candidates]))][:k]
    return {"dataset_id": dataset.metadata["dataset_id"], "metric": "cosine", "space": space(dataset),
            "candidate_scope": "current_dataset", "candidate_count": len(candidates), "requested_k": k,
            "returned_count": len(order), "results": [
                {"id": int(i), "word": dataset.words[i], "score": float(np.clip(scores[i], -1, 1))} for i in order]}


def neighbors(dataset: Dataset, word: str, k: int) -> dict:
    i = ids_for(dataset, [word])[0]
    return rank(dataset, dataset.units[i], {i}, k)


def analogy(dataset: Dataset, positive: list[str], negative: list[str], k: int, exclude: bool) -> dict:
    pos = ids_for(dataset, positive)
    neg = ids_for(dataset, negative)
    target = dataset.vectors[pos].sum(axis=0) - dataset.vectors[neg].sum(axis=0)
    scale = np.linalg.norm(dataset.vectors[pos + neg], axis=1).sum()
    norm = np.linalg.norm(target)
    if norm <= 1e-12 * max(1.0, scale):
        raise DomainError(400, "ZERO_TARGET_VECTOR", "向量运算的结果接近零，无法计算余弦方向。")
    return rank(dataset, target / norm, set(pos + neg) if exclude else set(), k)

