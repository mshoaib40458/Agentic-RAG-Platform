"""Build a starter evaluation dataset from past, successful queries.

Run from the ``backend`` directory::

    python scripts/build_eval_dataset.py --output data/eval/dataset.jsonl --limit 200

Each completed query that produced citations becomes one JSONL item:

* ``question`` - the original question
* ``relevant_document_ids`` - the distinct documents cited in the answer
* ``expected_answer`` - the answer that was produced (refine by hand before use)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.core.constants import QueryStatus  # noqa: E402
from app.db.models.query import Query  # noqa: E402
from app.db.session import AsyncSessionLocal, dispose_engine  # noqa: E402


async def build(output: Path, limit: int) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Query)
            .where(Query.status == QueryStatus.COMPLETED.value)
            .options(selectinload(Query.answer))
            .order_by(Query.created_at.desc())
            .limit(limit)
        )
        rows = list((await session.execute(stmt)).scalars().all())

    lines: list[str] = []
    for row in rows:
        if row.answer is None:
            continue
        document_ids = sorted(
            {
                str(citation.get("document_id"))
                for citation in row.answer.citations
                if citation.get("document_id")
            }
        )
        if not document_ids:
            continue
        lines.append(
            json.dumps(
                {
                    "question": row.question,
                    "relevant_document_ids": document_ids,
                    "relevant_chunk_ids": [],
                    "expected_answer": row.answer.content,
                },
                ensure_ascii=False,
            )
        )

    content = "\n".join(lines) + ("\n" if lines else "")
    await asyncio.to_thread(output.write_text, content, "utf-8")
    return len(lines)

async def _main(args: argparse.Namespace) -> int:
    try:
        return await build(Path(args.output), args.limit)
    finally:
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="data/eval/dataset.jsonl")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    count = asyncio.run(_main(args))
    print(f"Wrote {count} evaluation item(s) to {args.output}")
    if count == 0:
        print("No completed queries with citations found. Ask questions first, then re-run.")


if __name__ == "__main__":
    main()
