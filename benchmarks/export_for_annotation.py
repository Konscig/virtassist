"""Выгрузка QuestionAnswer для ручной аннотации.

Создаёт CSV файл с вопросами и ответами для последующей ручной разметки.
"""

from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parent.parent))

from qa.config import Config
from qa.database import QuestionAnswer, create_engine

logger = logging.getLogger(__name__)


ANNOTATION_FIELDS = [
    ("answer_type", "Тип ответа: 1=пустой, 2=не найден, 3=ошибка, 4=нормальный"),
    ("answer_relevance", "Релевантность ответа вопросу: 0=нет, 1=да, 2=частично"),
    ("url_relevance", "Релевантность URL вопросу: 0=нет, 1=да, 2=частично"),
    ("answer_url_relevance", "Релевантность ответа URL: 0=нет, 1=да, 2=частично"),
    ("notes", "Заметки"),
]


def export_for_annotation(
    engine,
    output_path: Path,
    limit: int | None = None,
) -> dict[str, Any]:
    """Экспортировать QuestionAnswer для аннотации."""
    with Session(engine) as session:
        query = select(QuestionAnswer).order_by(QuestionAnswer.id)
        if limit:
            query = query.limit(limit)

        rows = session.scalars(query).all()

    fieldnames = [
        "id",
        "question",
        "answer",
        "confluence_url",
        "score",
        "user_id",
        "platform",
        "created_at",
    ]

    for field_name, _ in ANNOTATION_FIELDS:
        fieldnames.append(f"annotate_{field_name}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            platform = "unknown"
            if row.user:
                if row.user.vk_id:
                    platform = "vk"
                elif row.user.telegram_id:
                    platform = "telegram"

            data = {
                "id": row.id,
                "question": row.question or "",
                "answer": row.answer or "",
                "confluence_url": row.confluence_url or "",
                "score": row.score if row.score is not None else "",
                "user_id": row.user_id,
                "platform": platform,
                "created_at": row.created_at.isoformat() if row.created_at else "",
            }

            for field_name, _ in ANNOTATION_FIELDS:
                data[f"annotate_{field_name}"] = ""

            writer.writerow(data)

    logger.info("Экспортировано %d вопросов в %s", len(rows), output_path)

    return {
        "total_rows": len(rows),
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
        default="benchmarks/data/annotation_dataset.csv",
        help="Путь для CSV файла",
    )
    args = parser.parse_args()

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
    for field_name, description in ANNOTATION_FIELDS:
        print(f"  - {field_name}: {description}")


if __name__ == "__main__":
    main()
