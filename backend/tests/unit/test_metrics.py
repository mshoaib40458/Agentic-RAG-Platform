"""Retrieval metric correctness (SRS FR-052)."""

from __future__ import annotations

from app.evaluation.metrics import (
    MetricAccumulator,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_at_k():
    assert recall_at_k(["a", "b", "c"], {"a", "c"}, 3) == 1.0
    assert recall_at_k(["a"], {"a", "b"}, 1) == 0.5
    assert recall_at_k(["x", "y"], {"a"}, 2) == 0.0
    assert recall_at_k([], set(), 5) == 0.0


def test_precision_at_k():
    assert precision_at_k(["a", "x"], {"a"}, 2) == 0.5
    assert precision_at_k(["a", "b"], {"a", "b"}, 2) == 1.0
    assert precision_at_k(["x"], {"a"}, 1) == 0.0


def test_reciprocal_rank():
    assert reciprocal_rank(["x", "a"], {"a"}) == 0.5
    assert reciprocal_rank(["a"], {"a"}) == 1.0
    assert reciprocal_rank(["x"], {"a"}) == 0.0


def test_accumulator_mean():
    accumulator = MetricAccumulator()
    accumulator.add(recall=1.0, precision=0.5, mrr=1.0)
    accumulator.add(recall=0.0, precision=0.0, mrr=0.0)
    mean = accumulator.mean()
    assert mean["recall_at_k"] == 0.5
    assert mean["precision_at_k"] == 0.25
    assert mean["mrr"] == 0.5
