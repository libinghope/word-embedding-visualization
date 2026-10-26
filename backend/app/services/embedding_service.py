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


def bridges(dataset: Dataset, a: list[str], b: list[str], k: int, threshold: float) -> dict:
    a, b = list(dict.fromkeys(a)), list(dict.fromkeys(b))
    groups = [ids_for(dataset, words) for words in (a, b)]
    centers = []
    for group in groups:
        center = dataset.units[group].mean(axis=0)
        norm = np.linalg.norm(center)
        if norm <= 1e-12:
            raise DomainError(400, 'ZERO_DOMAIN_VECTOR', '领域中心接近零，请更换输入词。')
        centers.append(center / norm)
    sa, sb = [dataset.units @ center for center in centers]
    score = np.minimum(sa, sb)
    excluded = set(groups[0] + groups[1])
    candidates = np.array([i for i in range(len(dataset.words)) if i not in excluded], dtype=int)
    eligible = candidates[(sa[candidates] >= threshold) & (sb[candidates] >= threshold)]
    order = eligible[np.lexsort((eligible, -(sa[eligible] + sb[eligible]) / 2, -score[eligible]))][:k]
    return {'dataset_id': dataset.metadata['dataset_id'], 'algorithm_version': 'bridge-min-v1',
            'space': space(dataset), 'a': a, 'b': b, 'shared_inputs': [w for w in a if w in b],
            'candidate_scope': 'current_dataset', 'candidate_count': len(candidates), 'eligible_count': len(eligible),
            'threshold': threshold, 'requested_k': k, 'returned_count': len(order),
            'results': [{'id': int(i), 'word': dataset.words[i], 'sA': float(np.clip(sa[i], -1, 1)),
                         'sB': float(np.clip(sb[i], -1, 1)), 'bridge': float(np.clip(score[i], -1, 1)),
                         'evidence_status': 'vector_only'} for i in order]}


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

