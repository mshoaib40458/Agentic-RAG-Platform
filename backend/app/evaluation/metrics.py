"""Evaluation metrics (SRS FR-051 / 8.1).

Retrieval metrics operate on a ranked list of ids against a set of relevant ids.
Answer metrics compare generated text to a reference answer.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

_WORD_RE = re.compile(r"[a-z0-9]+")


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    hits = sum(1 for item in retrieved[:k] if item in relevant)
    return hits / len(relevant)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    top = retrieved[:k]
    if not top or not relevant:
        return 0.0
    hits = sum(1 for item in top if item in relevant)
    return hits / len(top)


def hit_rate_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """1.0 if any relevant item appears in the top-k, else 0.0."""
    if not relevant:
        return 0.0
    return 1.0 if any(item in relevant for item in retrieved[:k]) else 0.0


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for rank, item in enumerate(retrieved, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Binary-relevance normalised discounted cumulative gain at k."""
    if not relevant:
        return 0.0
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, item in enumerate(retrieved[:k], start=1)
        if item in relevant
    )
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def token_f1(prediction: str, reference: str) -> float:
    """SQuAD-style token-overlap F1 between an answer and the reference."""
    pred_tokens = _tokenize(prediction)
    ref_tokens = _tokenize(reference)
    if not pred_tokens or not ref_tokens:
        return 0.0
    overlap = Counter(pred_tokens) & Counter(ref_tokens)
    common = sum(overlap.values())
    if common == 0:
        return 0.0
    precision = common / len(pred_tokens)
    recall = common / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


@dataclass(slots=True)
class MetricAccumulator:
    recall: float = 0.0
    precision: float = 0.0
    mrr: float = 0.0
    ndcg: float = 0.0
    hit_rate: float = 0.0
    answer_f1: float = 0.0
    answer_count: int = 0
    count: int = 0

    def add(
        self,
        *,
        recall: float,
        precision: float,
        mrr: float,
        ndcg: float = 0.0,
        hit_rate: float = 0.0,
        answer_f1: float | None = None,
    ) -> None:
        self.recall += recall
        self.precision += precision
        self.mrr += mrr
        self.ndcg += ndcg
        self.hit_rate += hit_rate
        self.count += 1
        if answer_f1 is not None:
            self.answer_f1 += answer_f1
            self.answer_count += 1

    def mean(self) -> dict[str, float]:
        if self.count == 0:
            base = {
                "recall_at_k": 0.0,
                "precision_at_k": 0.0,
                "mrr": 0.0,
                "ndcg_at_k": 0.0,
                "hit_rate_at_k": 0.0,
            }
        else:
            base = {
                "recall_at_k": round(self.recall / self.count, 4),
                "precision_at_k": round(self.precision / self.count, 4),
                "mrr": round(self.mrr / self.count, 4),
                "ndcg_at_k": round(self.ndcg / self.count, 4),
                "hit_rate_at_k": round(self.hit_rate / self.count, 4),
            }
        if self.answer_count:
            base["answer_f1"] = round(self.answer_f1 / self.answer_count, 4)
        return base
