"""Выгрузка QuestionAnswer для ручной аннотации.

Создаёт JSON файл с вопросами и ответами для последующей ручной разметки.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

sys.path.insert(0, str(Path(__file__).parent.parent))

from qa.config import Config
from qa.database import QuestionAnswer, create_engine

logger = logging.getLogger(__name__)


ANNOTATION_FIELDS = {
    "answer_type": "Тип ответа: 1=пустой, 2=не найден, 3=ошибка, 4=нормальный",
    "answer_relevance": "Релевантность ответа вопросу: 0=нет, 1=да, 2=частично",
    "url_relevance": "Релевантность URL вопросу: 0=нет, 1=да, 2=частично",
    "answer_url_relevance": "Релевантность ответа URL: 0=нет, 1=да, 2=частично",
    "notes": "Заметки",
}


def export_for_annotation(
    engine,
    output_path: Path,
    limit: int | None = None,
) -> dict[str, Any]:
    """Экспортировать QuestionAnswer для аннотации в JSON."""
    with Session(engine) as session:
        query = (
            select(QuestionAnswer)
            .options(selectinload(QuestionAnswer.user))
            .order_by(QuestionAnswer.id)
        )
        if limit:
            query = query.limit(limit)

        rows = session.scalars(query).all()

    annotation_keys = list(ANNOTATION_FIELDS.keys())

    items = []
    for row in rows:
        platform = "unknown"
        if row.user:
            if row.user.vk_id:
                platform = "vk"
            elif row.user.telegram_id:
                platform = "telegram"

        answer = row.answer or ""
        confluence_url = row.confluence_url or ""

        item = {
            "id": row.id,
            "question": row.question or "",
            "answer": answer,
            "confluence_url": confluence_url,
            "score": row.score if row.score is not None else None,
            "user_id": row.user_id,
            "platform": platform,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

        for key in annotation_keys:
            item[f"annotate_{key}"] = None

        if not answer:
            item["annotate_answer_type"] = "1"
            item["annotate_answer_relevance"] = "0"
            item["annotate_answer_url_relevance"] = "0"

        if not confluence_url:
            item["annotate_url_relevance"] = "0"
            item["annotate_answer_url_relevance"] = "0"

        items.append(item)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    logger.info("Экспортировано %d вопросов в %s", len(items), output_path)

    return {
        "total_rows": len(items),
        "output_path": str(output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Выгрузка QuestionAnswer для ручной аннотации"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Лимит вопросов (по умолчанию все)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Путь для JSON файла (по умолчанию benchmarks/data/annotation_YYYYMMDD_HHMMSS.json)",
    )
    args = parser.parse_args()

    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"benchmarks/data/dataset_annotation_{timestamp}.json"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    result = export_for_annotation(engine, Path(args.output), limit=args.limit)

    print(f"\nЭкспорт завершён:")
    print(f"  Всего вопросов: {result['total_rows']}")
    print(f"  Файл: {result['output_path']}")
    print("\nПоля для аннотации:")
    for field_name, description in ANNOTATION_FIELDS.items():
        print(f"  - {field_name}: {description}")


if __name__ == "__main__":
    main()
