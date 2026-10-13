"""Sweep retrieval modes over an evaluation dataset and print a comparison table.

Run from the ``backend`` directory::

    python scripts/sweep_eval.py --dataset data/eval/dataset.jsonl

This is the offline counterpart to the ``/api/v1/evaluation`` endpoint and picks
up whichever embedding model / reranker the current ``.env`` selects, so it can
be used to A/B test retrieval configurations.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import AsyncSessionLocal, dispose_engine  # noqa: E402
from app.evaluation.dataset import load_dataset  # noqa: E402
from app.evaluation.runner import evaluate_dataset  # noqa: E402

DEFAULT_MODES = ["dense", "bm25", "hybrid", "hybrid_rerank"]


async def run_sweep(
    dataset: Path, modes: list[str], top_k: int, candidate_k: int
) -> list[dict]:
    items = load_dataset(dataset)
    results: list[dict] = []
    try:
        async with AsyncSessionLocal() as session:
            for mode in modes:
                results.append(
                    await evaluate_dataset(
                        session,
                        items,
                        mode=mode,
                        top_k=top_k,
                        candidate_k=candidate_k,
                    )
                )
    finally:
        await dispose_engine()
    return results


def print_table(results: list[dict]) -> None:
    header = (
        f"{'mode':<16}{'recall@k':>10}{'prec@k':>10}{'mrr':>8}"
        f"{'ndcg@k':>10}{'hit@k':>8}{'items':>8}"
    )
    print(header)
    print("-" * len(header))
    for result in results:
        metrics = result["metrics"]
        print(
            f"{result['mode']:<16}"
            f"{metrics['recall_at_k']:>10.3f}"
            f"{metrics['precision_at_k']:>10.3f}"
            f"{metrics['mrr']:>8.3f}"
            f"{metrics['ndcg_at_k']:>10.3f}"
            f"{metrics['hit_rate_at_k']:>8.3f}"
            f"{result['evaluated_items']:>8}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="data/eval/dataset.jsonl")
    parser.add_argument("--modes", default=",".join(DEFAULT_MODES))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=20)
    args = parser.parse_args()

    modes = [mode.strip() for mode in args.modes.split(",") if mode.strip()]
    results = asyncio.run(
        run_sweep(Path(args.dataset), modes, args.top_k, args.candidate_k)
    )
    print_table(results)


if __name__ == "__main__":
    main()
