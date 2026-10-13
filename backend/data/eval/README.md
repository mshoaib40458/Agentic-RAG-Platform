# Evaluation dataset

JSON Lines, one object per line. Labels may be document-level, chunk-level, or both
(chunk-level takes precedence). `expected_answer` is optional and enables answer-level
metrics.

```json
{"question": "...", "relevant_document_ids": ["doc-id"], "relevant_chunk_ids": [], "expected_answer": "..."}
```

- `question` (required, non-empty) — the query to evaluate.
- `relevant_document_ids` / `relevant_chunk_ids` — gold labels used for retrieval metrics.
- `expected_answer` (optional) — reference answer for `answer_f1`.

## Building a starter dataset

Generate items from past, successful queries (must run from the `backend` directory):

```powershell
python scripts/build_eval_dataset.py --output data/eval/dataset.jsonl --limit 200
```

Each completed query that produced citations becomes one item, using the citations as
document labels and the produced answer as `expected_answer`. Refine the result by hand
before using it as a regression suite.

## Running evaluation

Through the API (`POST /api/v1/evaluation`) or the CLI sweep:

```powershell
python scripts/sweep_eval.py --dataset data/eval/dataset.jsonl
```

Set pass/fail gates via the run `config`, e.g.:

```json
{"mode": "hybrid_rerank", "top_k": 5, "thresholds": {"recall_at_k": 0.6, "mrr": 0.7}}
```

`metrics.passed` is `false` and `metrics.threshold_failures` lists each metric below its
minimum when a gate is missed.

## Metrics

Retrieval: `recall_at_k`, `precision_at_k`, `mrr`, `ndcg_at_k`, `hit_rate_at_k`.
Answer (when `include_answer_metrics` is set and `expected_answer` present): `answer_f1`.
