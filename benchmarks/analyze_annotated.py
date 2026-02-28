"""Подсчёт аналитики на основе размеченного датасета.

После ручной аннотации запустите этот скрипт для получения детальной статистики.
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ANSWER_TYPE_MAP = {
    "1": "Пустой (answer пустой)",
    "2": "Ответ не найден",
    "3": "Ошибка (есть URL)",
    "4": "Нормальный ответ",
}

RELEVANCE_MAP = {
    "0": "Нет",
    "1": "Да",
    "2": "Частично",
}


def analyze_annotated_dataset(input_path: Path) -> dict[str, Any]:
    """Подсчитать аналитику на основе размеченного датасета."""
    with open(input_path, "r", encoding="utf-8") as f:
        rows = json.load(f)

    total = len(rows)

    answer_types = Counter()
    answer_relevances = Counter()
    url_relevances = Counter()
    answer_url_relevances = Counter()

    empty_answers = 0
    not_found_answers = 0
    error_answers = 0
    normal_answers = 0

    for row in rows:
        at = str(row.get("annotate_answer_type", "")).strip()
        ar = str(row.get("annotate_answer_relevance", "")).strip()
        ur = str(row.get("annotate_url_relevance", "")).strip()
        aur = str(row.get("annotate_answer_url_relevance", "")).strip()

        if at:
            answer_types[at] += 1
            if at == "1":
                empty_answers += 1
            elif at == "2":
                not_found_answers += 1
            elif at == "3":
                error_answers += 1
            elif at == "4":
                normal_answers += 1

        if ar:
            answer_relevances[ar] += 1
        if ur:
            url_relevances[ur] += 1
        if aur:
            answer_url_relevances[aur] += 1

    has_answer = sum(
        1 for r in rows if str(r.get("annotate_answer_type", "")).strip() in ("3", "4")
    )
    real_answer_rate = has_answer / total if total else 0

    relevant_answers = sum(
        1 for r in rows if str(r.get("annotate_answer_relevance", "")).strip() == "1"
    )
    relevant_urls = sum(
        1 for r in rows if str(r.get("annotate_url_relevance", "")).strip() == "1"
    )
    relevant_answer_url = sum(
        1
        for r in rows
        if str(r.get("annotate_answer_url_relevance", "")).strip() == "1"
    )

    by_platform = {}
    for row in rows:
        platform = row.get("platform", "unknown")
        if platform not in by_platform:
            by_platform[platform] = {
                "total": 0,
                "has_answer": 0,
                "relevant": 0,
            }
        by_platform[platform]["total"] += 1
        at = str(row.get("annotate_answer_type", "")).strip()
        ar = str(row.get("annotate_answer_relevance", "")).strip()
        if at in ("3", "4"):
            by_platform[platform]["has_answer"] += 1
        if ar == "1":
            by_platform[platform]["relevant"] += 1

    result = {
        "total_questions": total,
        "answer_type_distribution": {
            "empty": empty_answers,
            "not_found": not_found_answers,
            "error_with_url": error_answers,
            "normal": normal_answers,
        },
        "real_answer_rate": real_answer_rate,
        "answer_relevance": {
            "relevant": relevant_answers,
            "relevant_percent": relevant_answers / total * 100 if total else 0,
        },
        "url_relevance": {
            "relevant": relevant_urls,
            "relevant_percent": relevant_urls / total * 100 if total else 0,
        },
        "answer_url_relevance": {
            "relevant": relevant_answer_url,
            "relevant_percent": relevant_answer_url / total * 100 if total else 0,
        },
        "by_platform": by_platform,
    }

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Подсчёт аналитики на основе размеченного датасета"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="benchmarks/data/dataset_annotation.json",
        help="Путь к размеченному JSON файлу",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Путь для JSON отчёта (опционально)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Файл не найден: %s", input_path)
        return

    result = analyze_annotated_dataset(input_path)

    print("\n" + "=" * 60)
    print("АНАЛИТИКА ПО РАЗМЕЧЕННЫМ ДАННЫМ")
    print("=" * 60)

    print(f"\nВсего вопросов: {result['total_questions']}")

    print("\n--- ТИПЫ ОТВЕТОВ ---")
    at = result["answer_type_distribution"]
    print(
        f"  Пустой (answer пустой):    {at['empty']:5d} ({at['empty'] / result['total_questions'] * 100:5.1f}%)"
    )
    print(
        f"  Ответ не найден:           {at['not_found']:5d} ({at['not_found'] / result['total_questions'] * 100:5.1f}%)"
    )
    print(
        f"  Ошибка (есть URL):        {at['error_with_url']:5d} ({at['error_with_url'] / result['total_questions'] * 100:5.1f}%)"
    )
    print(
        f"  Нормальный ответ:          {at['normal']:5d} ({at['normal'] / result['total_questions'] * 100:5.1f}%)"
    )

    print(f"\n--- РЕАЛЬНЫЙ ПОКАЗАТЕЛЬ ОТВЕТОВ ---")
    print(
        f"  Вопросов с реальным ответом: {at['error_with_url'] + at['normal']} ({result['real_answer_rate'] * 100:.1f}%)"
    )

    print("\n--- РЕЛЕВАНТНОСТЬ ---")
    ar = result["answer_relevance"]
    print(
        f"  Ответ релевантен вопросу:     {ar['relevant']:5d} ({ar['relevant_percent']:.1f}%)"
    )

    ur = result["url_relevance"]
    print(
        f"  URL релевантен вопросу:      {ur['relevant']:5d} ({ur['relevant_percent']:.1f}%)"
    )

    aur = result["answer_url_relevance"]
    print(
        f"  Ответ релевантен URL:        {aur['relevant']:5d} ({aur['relevant_percent']:.1f}%)"
    )

    print("\n--- ПО ПЛАТФОРМАМ ---")
    for platform, data in result["by_platform"].items():
        has_rate = data["has_answer"] / data["total"] * 100 if data["total"] else 0
        rel_rate = data["relevant"] / data["total"] * 100 if data["total"] else 0
        print(
            f"  {platform:10s}: {data['total']:5d} вопросов, {has_rate:.1f}% с ответами, {rel_rate:.1f}% релевантных"
        )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nJSON отчёт сохранён: {output_path}")


if __name__ == "__main__":
    main()
