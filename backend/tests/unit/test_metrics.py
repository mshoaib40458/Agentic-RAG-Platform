"""Retrieval metric correctness (SRS FR-052)."""

from __future__ import annotations

import math

import pytest

from app.evaluation.metrics import (
    MetricAccumulator,
    hit_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    token_f1,
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


def test_ndcg_at_k():
    assert ndcg_at_k(["a", "b"], {"a"}, 2) == 1.0
    assert ndcg_at_k(["x", "a"], {"a"}, 2) == pytest.approx(1 / math.log2(3))
    assert ndcg_at_k(["x", "y"], {"a"}, 2) == 0.0
    assert ndcg_at_k([], set(), 5) == 0.0


def test_hit_rate_at_k():
    assert hit_rate_at_k(["x", "a"], {"a"}, 2) == 1.0
    assert hit_rate_at_k(["x", "y"], {"a"}, 2) == 0.0


def test_token_f1():
    assert token_f1("the quick brown fox", "the quick brown fox") == 1.0
    assert token_f1("the cat", "a dog") == 0.0
    assert 0.0 < token_f1("the quick fox", "the quick brown fox") < 1.0


def test_accumulator_reports_answer_f1_when_present():
    accumulator = MetricAccumulator()
    accumulator.add(recall=1.0, precision=1.0, mrr=1.0, answer_f1=0.5)
    accumulator.add(recall=1.0, precision=1.0, mrr=1.0)
    mean = accumulator.mean()
    assert mean["answer_f1"] == 0.5
    assert mean["ndcg_at_k"] == 0.0
