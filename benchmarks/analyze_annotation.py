#!/usr/bin/env python3
"""Скрипт для анализа аннотированного датасета."""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def load_annotated_dataset(path: Path) -> List[Dict]:
    """Загрузить аннотированный датасет."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def count_annotated_items(items: List[Dict]) -> int:
    """Посчитать количество аннотированных элементов."""
    return sum(1 for item in items if item.get("annotate_is_small_talk") is not None)


def calculate_real_metrics(items: List[Dict]) -> Dict:
    """Посчитать реальные метрики на основе аннотированных данных."""
    annotated_items = [
        item for item in items if item.get("annotate_is_small_talk") is not None
    ]
    total = len(annotated_items)

    metrics = {
        "total_annotated": total,
        "empty_answers": {"count": 0, "percent": 0.0},
        "answer_types": {"без_ответа": 0, "некорректные": 0, "релевантные": 0},
        "question_types": {"по_делу": 0, "small_talk": 0, "про_вопрошалыча": 0},
        "url_relevance": {"url_релевантен": 0, "ответ_использует_url": 0},
        "has_source": {"has_source": 0, "without_source": 0},
        "user_scores": {"score_5": 0, "score_1": 0, "total_with_score": 0},
    }

    for item in annotated_items:
        answer = item.get("answer", "") or ""

        if not answer:
            metrics["empty_answers"]["count"] += 1

        answer_type = item.get("annotate_answer_type")
        if answer_type == 1:
            metrics["answer_types"]["без_ответа"] += 1
        elif answer_type == 2:
            metrics["answer_types"]["некорректные"] += 1
        elif answer_type == 3:
            metrics["answer_types"]["релевантные"] += 1

        is_small_talk = item.get("annotate_is_small_talk")
        if is_small_talk == 0:
            metrics["question_types"]["по_делу"] += 1
        elif is_small_talk == 1:
            metrics["question_types"]["small_talk"] += 1
        elif is_small_talk == 2:
            metrics["question_types"]["про_вопрошалыча"] += 1

        has_source = item.get("annotate_has_source")
        if has_source == 1:
            metrics["has_source"]["has_source"] += 1
            url_relevance = item.get("annotate_url_relevance")
            if url_relevance == 1:
                metrics["url_relevance"]["url_релевантен"] += 1

            answer_url_relevance = item.get("annotate_answer_url_relevance")
            if answer_url_relevance == 1:
                metrics["url_relevance"]["ответ_использует_url"] += 1
        else:
            metrics["has_source"]["without_source"] += 1

        score = item.get("score")
        if score:
            metrics["user_scores"]["total_with_score"] += 1
            if score == 5:
                metrics["user_scores"]["score_5"] += 1
            elif score == 1:
                metrics["user_scores"]["score_1"] += 1

    metrics["empty_answers"]["percent"] = (
        metrics["empty_answers"]["count"] / total * 100 if total > 0 else 0
    )

    return metrics


def calculate_percentages(metrics: Dict, total: int) -> Dict:
    """Рассчитать проценты для всех метрик."""
    percentages = {}

    for key, value in metrics["answer_types"].items():
        percentages[f"answer_type_{key}"] = value / total * 100 if total > 0 else 0

    for key, value in metrics["question_types"].items():
        percentages[f"question_type_{key}"] = value / total * 100 if total > 0 else 0

    for key, value in metrics["url_relevance"].items():
        percentages[f"url_relevance_{key}"] = value / total * 100 if total > 0 else 0

    for key, value in metrics["has_source"].items():
        percentages[f"has_source_{key}"] = value / total * 100 if total > 0 else 0

    if metrics["user_scores"]["total_with_score"] > 0:
        percentages["score_5_percent"] = (
            metrics["user_scores"]["score_5"]
            / metrics["user_scores"]["total_with_score"]
            * 100
        )
        percentages["score_1_percent"] = (
            metrics["user_scores"]["score_1"]
            / metrics["user_scores"]["total_with_score"]
            * 100
        )

    return percentages


def create_real_metrics_report(metrics: Dict, percentages: Dict) -> Dict:
    """Создать отчет с реальными метриками."""
    report = {
        "dataset_info": {
            "total_records": metrics["total_annotated"],
            "description": "Аннотированные записи из выборки (~180 вопросов)",
        },
        "real_metrics": {
            "empty_answers": {
                "description": "Записи с пустым полем answer (answer = '')",
                "count": metrics["empty_answers"]["count"],
                "percent": round(metrics["empty_answers"]["percent"], 1),
                "formula": f"{metrics['empty_answers']['count']} / {metrics['total_annotated']} * 100 = {round(metrics['empty_answers']['percent'], 1)}%",
                "source": "РЕАЛЬНЫЕ данные из аннотированной выборки",
            },
            "answer_types": {
                "без_ответа": {
                    "count": metrics["answer_types"]["без_ответа"],
                    "percent": round(percentages["answer_type_без_ответа"], 1),
                    "source": "РЕАЛЬНЫЕ данные из annotate_answer_type = 1",
                },
                "некорректные": {
                    "count": metrics["answer_types"]["некорректные"],
                    "percent": round(percentages["answer_type_некорректные"], 1),
                    "source": "РЕАЛЬНЫЕ данные из annotate_answer_type = 2",
                },
                "релевантные": {
                    "count": metrics["answer_types"]["релевантные"],
                    "percent": round(percentages["answer_type_релевантные"], 1),
                    "source": "РЕАЛЬНЫЕ данные из annotate_answer_type = 3",
                },
            },
            "question_types": {
                "по_делу": {
                    "count": metrics["question_types"]["по_делу"],
                    "percent": round(percentages["question_type_по_делу"], 1),
                    "source": "РЕАЛЬНЫЕ данные из annotate_is_small_talk = 0",
                },
                "small_talk": {
                    "count": metrics["question_types"]["small_talk"],
                    "percent": round(percentages["question_type_small_talk"], 1),
                    "source": "РЕАЛЬНЫЕ данные из annotate_is_small_talk = 1",
                },
                "про_вопрошалыча": {
                    "count": metrics["question_types"]["про_вопрошалыча"],
                    "percent": round(percentages["question_type_про_вопрошалыча"], 1),
                    "source": "РЕАЛЬНЫЕ данные из annotate_is_small_talk = 2",
                },
            },
            "url_relevance": {
                "url_релевантен": {
                    "percent": round(
                        percentages.get("url_relevance_url_релевантен", 0), 1
                    ),
                    "count": metrics["url_relevance"]["url_релевантен"],
                    "source": "РЕАЛЬНЫЕ данные из annotate_url_relevance = 1",
                },
                "ответ_использует_url": {
                    "percent": round(
                        percentages.get("url_relevance_ответ_использует_url", 0), 1
                    ),
                    "count": metrics["url_relevance"]["ответ_использует_url"],
                    "source": "РЕАЛЬНЫЕ данные из annotate_answer_url_relevance = 1",
                },
            },
            "has_source": {
                "has_source": {
                    "count": metrics["has_source"]["has_source"],
                    "percent": round(percentages["has_source_has_source"], 1),
                    "source": "РЕАЛЬНЫЕ данные из annotate_has_source = 1",
                },
                "without_source": {
                    "count": metrics["has_source"]["without_source"],
                    "percent": round(percentages["has_source_without_source"], 1),
                    "source": "РЕАЛЬНЫЕ данные из annotate_has_source = 0",
                },
            },
            "user_scores": {
                "total_with_score": metrics["user_scores"]["total_with_score"],
                "score_5": metrics["user_scores"]["score_5"],
                "score_1": metrics["user_scores"]["score_1"],
                "score_5_percent": round(percentages.get("score_5_percent", 0), 1),
                "score_1_percent": round(percentages.get("score_1_percent", 0), 1),
                "formula_5": f"{metrics['user_scores']['score_5']} / {metrics['user_scores']['total_with_score']} * 100 = {round(percentages.get('score_5_percent', 0), 1)}%",
                "formula_1": f"{metrics['user_scores']['score_1']} / {metrics['user_scores']['total_with_score']} * 100 = {round(percentages.get('score_1_percent', 0), 1)}%",
                "source": "РЕАЛЬНЫЕ данные из поля score",
            },
        },
        "generated_at": datetime.now().isoformat(),
    }

    return report


def main():
    """Главная функция."""
    dataset_path = Path(
        "/Users/masha/src/github.com/webmasha/voproshalych-personal/Submodules/voproshalych/benchmarks/data/dataset_from_20250601_to_20260228_20260303_082311_annotated_annotated.json"
    )
    output_dir = Path(
        "/Users/masha/src/github.com/webmasha/voproshalych-personal/2026_benchmarks/2026_analysis/annotaciya-i-razmetka-real'nogo-korpusa-pol'zovatel'skih-dannyh"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Загрузка аннотированного датасета...")
    items = load_annotated_dataset(dataset_path)
    print(f"Всего записей в датасете: {len(items)}")

    annotated_count = count_annotated_items(items)
    print(f"Аннотированных записей: {annotated_count}")

    print("\nРасчет метрик...")
    metrics = calculate_real_metrics(items)
    percentages = calculate_percentages(metrics, metrics["total_annotated"])

    print("\nСоздание отчета...")
    report = create_real_metrics_report(metrics, percentages)

    print("\nМетрики:")
    print(f"  Аннотировано: {metrics['total_annotated']}")
    print(
        f"  Пустых ответов: {metrics['empty_answers']['count']} ({metrics['empty_answers']['percent']:.1f}%)"
    )
    print(f"  Типы ответов:")
    print(
        f"    Без ответа: {metrics['answer_types']['без_ответа']} ({percentages['answer_type_без_ответа']:.1f}%)"
    )
    print(
        f"    Некорректные: {metrics['answer_types']['некорректные']} ({percentages['answer_type_некорректные']:.1f}%)"
    )
    print(
        f"    Релевантные: {metrics['answer_types']['релевантные']} ({percentages['answer_type_релевантные']:.1f}%)"
    )
    print(f"  Типы вопросов:")
    print(
        f"    По делу: {metrics['question_types']['по_делу']} ({percentages['question_type_по_делу']:.1f}%)"
    )
    print(
        f"    Small talk: {metrics['question_types']['small_talk']} ({percentages['question_type_small_talk']:.1f}%)"
    )
    print(
        f"    Про Вопрошалыча: {metrics['question_types']['про_вопрошалыча']} ({percentages['question_type_про_вопрошалыча']:.1f}%)"
    )

    output_path = output_dir / "real_metrics_report.json"
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nОтчет сохранен: {output_path}")


if __name__ == "__main__":
    main()
