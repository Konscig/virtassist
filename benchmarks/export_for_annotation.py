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

# Load URL to title mapping
CONFLUENCE_URLS_JSON = Path(__file__).parent / "data" / "confluence_urls.json"
try:
    with open(CONFLUENCE_URLS_JSON, "r", encoding="utf-8") as f:
        CONFLUENCE_URLS = json.load(f)
except FileNotFoundError:
    logger.warning(
        f"Файл {CONFLUENCE_URLS_JSON} не найден, названия URL не будут добавлены"
    )
    CONFLUENCE_URLS = {}


ANNOTATION_FIELDS = {
    "answer_type": "Тип ответа: 1=пустой, 2=нет ответа/некорректный, 3=нормальный",
    "has_source": "Наличие источника: 0=нет, 1=есть",
    "url_relevance": "Релевантность URL: 0=нет, 1=да",
    "answer_url_relevance": "Релевантность ответа URL: 0=нет, 1=да",
    "is_small_talk": "Small talk: 0=по делу, 1=small talk, 2=про Вопрошалыча",
}


def export_for_annotation(
    engine,
    output_path: Path,
    limit: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict[str, Any]:
    """Экспортировать QuestionAnswer для аннотации в JSON."""
    with Session(engine) as session:
        query = select(QuestionAnswer).options(selectinload(QuestionAnswer.user))

        if start_date:
            query = query.where(QuestionAnswer.created_at >= start_date)
        if end_date:
            query = query.where(QuestionAnswer.created_at <= end_date)

        query = query.order_by(QuestionAnswer.id)

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

        # Get title for the URL if exists
        source_title = ""
        if confluence_url and confluence_url in CONFLUENCE_URLS:
            source_title = CONFLUENCE_URLS[confluence_url].get("title", "")

        item = {
            "id": row.id,
            "question": row.question or "",
            "answer": answer,
            "confluence_url": confluence_url,
            "source_title": source_title,
            "score": row.score if row.score is not None else None,
            "user_id": row.user_id,
            "platform": platform,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

        for key in annotation_keys:
            item[f"annotate_{key}"] = None

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
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Начальная дата (формат YYYY-MM-DD, например 2025-06-01)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="Конечная дата (формат YYYY-MM-DD, например 2026-02-28)",
    )
    args = parser.parse_args()

    start_date = None
    end_date = None

    if args.start_date:
        try:
            start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
        except ValueError:
            logger.error("Неверный формат даты: %s", args.start_date)
            return

    if args.end_date:
        try:
            end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
            end_date = end_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            logger.error("Неверный формат даты: %s", args.end_date)
            return

    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if start_date or end_date:
            date_part = ""
            if start_date:
                date_part += f"_from_{start_date.strftime('%Y%m%d')}"
            if end_date:
                date_part += f"_to_{end_date.strftime('%Y%m%d')}"
            args.output = f"benchmarks/data/dataset{date_part}_{timestamp}.json"
        else:
            args.output = f"benchmarks/data/dataset_annotation_{timestamp}.json"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    result = export_for_annotation(
        engine,
        Path(args.output),
        limit=args.limit,
        start_date=start_date,
        end_date=end_date,
    )

    print(f"\nЭкспорт завершён:")
    print(f"  Всего вопросов: {result['total_rows']}")
    print(f"  Файл: {result['output_path']}")
    print("\nПоля для аннотации:")
    for field_name, description in ANNOTATION_FIELDS.items():
        print(f"  - {field_name}: {description}")


if __name__ == "__main__":
    main()
