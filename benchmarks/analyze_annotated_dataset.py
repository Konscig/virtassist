"""Анализ аннотированного датасета для Domain Insights."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from collections import Counter

logger = logging.getLogger(__name__)


def analyze_annotated_dataset(
    input_path: Path,
) -> dict[str, Any]:
    """Анализировать аннотированный датасет и вычислить метрики."""
    with open(input_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    if not items:
        return {"error": "Пустой датасет"}

    total = len(items)

    # Даты
    dates = []
    for item in items:
        created_at = item.get("created_at")
        if created_at:
            dates.append(created_at[:10])

    date_counts = Counter(dates)
    min_date = min(dates) if dates else None
    max_date = max(dates) if dates else None

    # Метрики
    empty_answers = 0  # answer_type = 1
    bad_answers = 0  # answer_type = 2
    good_answers = 0  # answer_type = 3

    with_sources = 0
    without_sources = 0

    url_relevant = 0  # url_relevance = 1
    url_not_relevant = 0  # url_relevance = 0

    answer_url_relevant = 0  # answer_url_relevance = 1
    answer_url_not_relevant = 0  # answer_url_relevance = 0

    on_topic = 0  # is_small_talk = 0
    small_talk = 0  # is_small_talk = 1
    about_bot = 0  # is_small_talk = 2

    for item in items:
        # answer_type
        at = str(item.get("annotate_answer_type", ""))
        if at == "1":
            empty_answers += 1
        elif at == "2":
            bad_answers += 1
        elif at == "3":
            good_answers += 1

        # has_source
        hs = str(item.get("annotate_has_source", ""))
        if hs == "1":
            with_sources += 1
        elif hs == "0":
            without_sources += 1

        # url_relevance
        ur = str(item.get("annotate_url_relevance", ""))
        if ur == "1":
            url_relevant += 1
        else:
            url_not_relevant += 1

        # answer_url_relevance
        aur = str(item.get("annotate_answer_url_relevance", ""))
        if aur == "1":
            answer_url_relevant += 1
        else:
            answer_url_not_relevant += 1

        # is_small_talk
        st = str(item.get("annotate_is_small_talk", ""))
        if st == "0":
            on_topic += 1
        elif st == "1":
            small_talk += 1
        elif st == "2":
            about_bot += 1

    # Вычисления
    good_rate = (good_answers / total * 100) if total > 0 else 0
    bad_rate = (bad_answers / total * 100) if total > 0 else 0
    empty_rate = (empty_answers / total * 100) if total > 0 else 0

    with_source_rate = (with_sources / total * 100) if total > 0 else 0

    url_relevant_rate = (url_relevant / total * 100) if total > 0 else 0
    answer_url_relevant_rate = (answer_url_relevant / total * 100) if total > 0 else 0

    small_talk_rate = (small_talk / total * 100) if total > 0 else 0
    about_bot_rate = (about_bot / total * 100) if total > 0 else 0
    on_topic_rate = (on_topic / total * 100) if total > 0 else 0

    # Вопросы с ответом (answer_type = 2 или 3)
    answered = bad_answers + good_answers
    answered_with_good = good_answers
    good_answer_rate = (answered_with_good / answered * 100) if answered > 0 else 0

    result = {
        "period": {
            "start": min_date,
            "end": max_date,
        },
        "total_questions": total,
        "answer_type": {
            "empty": empty_answers,
            "empty_percent": round(empty_rate, 1),
            "bad": bad_answers,
            "bad_percent": round(bad_rate, 1),
            "good": good_answers,
            "good_percent": round(good_rate, 1),
        },
        "sources": {
            "with_source": with_sources,
            "with_source_percent": round(with_source_rate, 1),
            "without_source": without_sources,
        },
        "url_relevance": {
            "relevant": url_relevant,
            "relevant_percent": round(url_relevant_rate, 1),
            "not_relevant": url_not_relevant,
        },
        "answer_url_relevance": {
            "relevant": answer_url_relevant,
            "relevant_percent": round(answer_url_relevant_rate, 1),
            "not_relevant": answer_url_not_relevant,
        },
        "question_types": {
            "on_topic": on_topic,
            "on_topic_percent": round(on_topic_rate, 1),
            "small_talk": small_talk,
            "small_talk_percent": round(small_talk_rate, 1),
            "about_bot": about_bot,
            "about_bot_percent": round(about_bot_rate, 1),
        },
        "good_answer_rate": round(good_answer_rate, 1),
        "date_distribution": dict(date_counts),
    }

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Анализ аннотированного датасета")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Путь к JSON файлу с аннотированными данными",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Путь для сохранения результатов (по умолчанию в reports/)",
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

    logger.info("Анализ: %s", input_path)
    result = analyze_annotated_dataset(input_path)

    if args.output:
        output_path = Path(args.output)
    else:
        reports_dir = Path("benchmarks/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = reports_dir / f"domain_insights_{timestamp}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info("Сохранено в: %s", output_path)

    # Вывод в консоль
    print("\n" + "=" * 50)
    print("АНАЛИЗ АННОТИРОВАННОГО ДАТАСЕТА")
    print("=" * 50)
    print(f"\nПериод: {result['period']['start']} - {result['period']['end']}")
    print(f"\nВсего вопросов: {result['total_questions']}")

    print("\n--- Типы ответов ---")
    at = result["answer_type"]
    print(f"Пустые (1): {at['empty']} ({at['empty_percent']}%)")
    print(f"Некорректные (2): {at['bad']} ({at['bad_percent']}%)")
    print(f"Нормальные (3): {at['good']} ({at['good_percent']}%)")

    print("\n--- Источники ---")
    src = result["sources"]
    print(f"С источником: {src['with_source']} ({src['with_source_percent']}%)")
    print(f"Без источника: {src['without_source']}")

    print("\n--- Релевантность URL ---")
    url = result["url_relevance"]
    print(f"URL релевантен вопросу: {url['relevant']} ({url['relevant_percent']}%)")
    print(f"URL не релевантен: {url['not_relevant']}")

    aur = result["answer_url_relevance"]
    print(f"\nОтвет использует URL: {aur['relevant']} ({aur['relevant_percent']}%)")
    print(f"Ответ не использует URL: {aur['not_relevant']}")

    print("\n--- Типы вопросов ---")
    qt = result["question_types"]
    print(f"По делу: {qt['on_topic']} ({qt['on_topic_percent']}%)")
    print(f"Small talk: {qt['small_talk']} ({qt['small_talk_percent']}%)")
    print(f"Про Вопрошалыча: {qt['about_bot']} ({qt['about_bot_percent']}%)")

    print("\n--- Нормальные ответы ---")
    print(f"Процент нормальных ответов отвеченных: {result['good_answer_rate']}%")


if __name__ == "__main__":
    main()
