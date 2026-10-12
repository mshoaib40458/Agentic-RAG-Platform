"""Ranking metrics for retrieval evaluation (SRS FR-052 / 8.1).

All functions operate on a single query's ranked list of retrieved ids against a
set of relevant ids, then the runner aggregates the per-query values.
"""

from __future__ import annotations

from dataclasses import dataclass


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


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for rank, item in enumerate(retrieved, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


@dataclass(slots=True)
class MetricAccumulator:
    recall: float = 0.0
    precision: float = 0.0
    mrr: float = 0.0
    count: int = 0

    def add(self, *, recall: float, precision: float, mrr: float) -> None:
        self.recall += recall
        self.precision += precision
        self.mrr += mrr
        self.count += 1

    def mean(self) -> dict[str, float]:
        if self.count == 0:
            return {"recall_at_k": 0.0, "precision_at_k": 0.0, "mrr": 0.0}
        return {
            "recall_at_k": round(self.recall / self.count, 4),
            "precision_at_k": round(self.precision / self.count, 4),
            "mrr": round(self.mrr / self.count, 4),
        }
