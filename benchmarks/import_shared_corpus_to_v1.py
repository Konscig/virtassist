"""Import shared frozen corpus snapshot into v1 `chunk` table."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from qa.config import Config
from qa.database import create_engine

logger = logging.getLogger(__name__)


def import_shared_corpus(input_path: Path, clear_table: bool) -> dict:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    chunks = payload.get("chunks", [])

    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)

    imported = 0
    with engine.begin() as conn:
        if clear_table:
            conn.execute(text("TRUNCATE TABLE chunk RESTART IDENTITY CASCADE"))

        for item in chunks:
            canonical_id = int(item["canonical_chunk_id"])
            embedding = item.get("embedding")
            if isinstance(embedding, list) and embedding:
                conn.execute(
                    text(
                        """
                        INSERT INTO chunk (id, confluence_url, text, embedding)
                        VALUES (:id, :confluence_url, :text, CAST(:embedding AS vector))
                        ON CONFLICT (id) DO UPDATE SET
                            confluence_url = EXCLUDED.confluence_url,
                            text = EXCLUDED.text,
                            embedding = EXCLUDED.embedding
                        """
                    ),
                    {
                        "id": canonical_id,
                        "confluence_url": item.get("source_url"),
                        "text": item.get("text", ""),
                        "embedding": "[" + ",".join(map(str, embedding)) + "]",
                    },
                )
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO chunk (id, confluence_url, text)
                        VALUES (:id, :confluence_url, :text)
                        ON CONFLICT (id) DO UPDATE SET
                            confluence_url = EXCLUDED.confluence_url,
                            text = EXCLUDED.text
                        """
                    ),
                    {
                        "id": canonical_id,
                        "confluence_url": item.get("source_url"),
                        "text": item.get("text", ""),
                    },
                )
            imported += 1

    return {
        "input_path": str(input_path),
        "clear_table": clear_table,
        "imported_chunks": imported,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import shared corpus into v1 chunk table"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="benchmarks/data/shared_corpus_v2.json",
        help="Path to shared corpus JSON",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Truncate `chunk` table before import",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    summary = import_shared_corpus(input_path=Path(args.input), clear_table=args.clear)

    logger.info("Import summary: %s", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
