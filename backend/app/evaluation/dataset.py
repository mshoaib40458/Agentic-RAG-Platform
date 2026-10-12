"""Evaluation dataset loading (SRS FR-051 / 8.1).

Dataset is JSON Lines, one object per line::

    {
      "question": "...",
      "relevant_document_ids": ["doc-id", "..."],   # document-level labels
      "relevant_chunk_ids": ["chunk-id", "..."],     # optional chunk-level labels
      "expected_answer": "..."                        # optional, for answer metrics
    }

Chunk-level labels take precedence over document-level labels when present.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.core.exceptions import IngestionError


@dataclass(slots=True)
class EvalItem:
    question: str
    relevant_document_ids: list[str] = field(default_factory=list)
    relevant_chunk_ids: list[str] = field(default_factory=list)
    expected_answer: str | None = None

    @property
    def has_labels(self) -> bool:
        return bool(self.relevant_chunk_ids or self.relevant_document_ids)


def load_dataset(path: Path) -> list[EvalItem]:
    if not path.exists():
        raise IngestionError(
            f"Evaluation dataset not found at {path}.", code="eval_dataset_missing"
        )
    items: list[EvalItem] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise IngestionError(
                f"Invalid JSON on line {line_number} of the dataset.", code="eval_dataset_invalid"
            ) from exc
        items.append(
            EvalItem(
                question=record["question"],
                relevant_document_ids=list(record.get("relevant_document_ids") or []),
                relevant_chunk_ids=list(record.get("relevant_chunk_ids") or []),
                expected_answer=record.get("expected_answer"),
            )
        )
    if not items:
        raise IngestionError("Evaluation dataset is empty.", code="eval_dataset_empty")
    return items
