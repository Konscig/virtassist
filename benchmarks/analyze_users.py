#!/usr/bin/env python3
"""Скрипт для анализа статистики пользователей из БД Вопрошалыча."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    """Подключиться к базе данных."""
    return psycopg2.connect(
        host="localhost",
        port=5432,
        database="virtassist",
        user="postgres",
        password="postgres",
    )


def get_user_platform(user_id: int, conn) -> str:
    """Определить платформу пользователя по ID."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 
                CASE 
                    WHEN vk_id IS NOT NULL THEN 'vk'
                    WHEN telegram_id IS NOT NULL THEN 'telegram'
                    ELSE 'unknown'
                END as platform
            FROM "user"
            WHERE id = %s
            """,
            (user_id,),
        )
        result = cur.fetchone()
        return result[0] if result else "unknown"


def get_user_statistics(conn) -> Dict:
    """Получить статистику по пользователям."""
    stats = {}

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT 
                COUNT(DISTINCT u.id) as total_users,
                COUNT(DISTINCT CASE WHEN q.id IS NOT NULL THEN u.id END) as users_with_questions
            FROM "user" u
            LEFT JOIN question_answer q ON u.id = q.user_id
            """
        )
        row = cur.fetchone()
        stats["total_users"] = row["total_users"]
        stats["users_with_questions"] = row["users_with_questions"]

        cur.execute(
            """
            SELECT 
                COUNT(*) as total_questions
            FROM question_answer
            """
        )
        row = cur.fetchone()
        stats["total_questions"] = row["total_questions"]

        cur.execute(
            """
            SELECT 
                AVG(q_count) as avg_questions_per_user
            FROM (
                SELECT COUNT(*) as q_count
                FROM question_answer
                GROUP BY user_id
            ) subq
            """
        )
        row = cur.fetchone()
        stats["avg_questions_per_user"] = (
            round(row["avg_questions_per_user"], 2)
            if row["avg_questions_per_user"]
            else 0
        )

        cur.execute(
            """
            SELECT 
                MIN(q_count) as min_questions,
                MAX(q_count) as max_questions,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY q_count) as median_questions
            FROM (
                SELECT COUNT(*) as q_count
                FROM question_answer
                GROUP BY user_id
            ) subq
            """
        )
        row = cur.fetchone()
        stats["min_questions_per_user"] = row["min_questions"] or 0
        stats["max_questions_per_user"] = row["max_questions"] or 0
        stats["median_questions_per_user"] = (
            round(row["median_questions"], 2) if row["median_questions"] else 0
        )

    return stats


def get_platforms_over_time(conn) -> Dict[str, List[Tuple]]:
    """Получить количество пользователей по платформам за все время."""
    platforms_data = {
        "vk": [],
        "telegram": [],
        "max": [],
        "unknown": [],
    }

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT 
                DATE(u.created_at) as date,
                COUNT(*) as count
            FROM "user" u
            WHERE vk_id IS NOT NULL
            GROUP BY DATE(u.created_at)
            ORDER BY date
            """
        )
        for row in cur.fetchall():
            platforms_data["vk"].append((row["date"], row["count"]))

        cur.execute(
            """
            SELECT 
                DATE(u.created_at) as date,
                COUNT(*) as count
            FROM "user" u
            WHERE telegram_id IS NOT NULL
            GROUP BY DATE(u.created_at)
            ORDER BY date
            """
        )
        for row in cur.fetchall():
            platforms_data["telegram"].append((row["date"], row["count"]))

        cur.execute(
            """
            SELECT 
                DATE(u.created_at) as date,
                COUNT(*) as count
            FROM "user" u
            WHERE vk_id IS NULL AND telegram_id IS NULL
            GROUP BY DATE(u.created_at)
            ORDER BY date
            """
        )
        for row in cur.fetchall():
            platforms_data["unknown"].append((row["date"], row["count"]))

    platforms_data["max"] = []

    return platforms_data


def get_questions_per_user_distribution(conn) -> Dict[int, int]:
    """Получить распределение количества вопросов на пользователя."""
    distribution = {}

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT q_count, COUNT(*) as user_count
            FROM (
                SELECT COUNT(*) as q_count
                FROM question_answer
                GROUP BY user_id
            ) subq
            GROUP BY q_count
            ORDER BY q_count
            """
        )
        for row in cur.fetchall():
            distribution[row[0]] = row[1]

    return distribution


def plot_platforms_growth(platforms_data: Dict[str, List[Tuple]], output_path: Path):
    """Построить график роста пользователей по платформам."""
    plt.figure(figsize=(14, 8))

    colors = {
        "vk": "#4C75A9",
        "telegram": "#0088cc",
        "max": "#FF6B35",
        "unknown": "#95A5A6",
    }

    for platform, data in platforms_data.items():
        if data:
            dates, counts = zip(*data)
            cumulative_counts = []
            total = 0
            for count in counts:
                total += count
                cumulative_counts.append(total)
            plt.plot(
                dates,
                cumulative_counts,
                label=platform.upper(),
                color=colors[platform],
                linewidth=2,
                marker="o",
                markersize=4,
            )

    plt.title(
        "Количество пользователей по платформам за все время",
        fontsize=16,
        fontweight="bold",
        pad=20,
    )
    plt.xlabel("Дата", fontsize=12)
    plt.ylabel("Количество пользователей (накопительно)", fontsize=12)
    plt.legend(loc="upper left", fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"График по платформам сохранен: {output_path}")


def plot_questions_distribution(distribution: Dict[int, int], output_path: Path):
    """Построить распределение количества вопросов на пользователя."""
    plt.figure(figsize=(14, 8))

    sorted_dist = sorted(distribution.items())
    x = [item[0] for item in sorted_dist]
    y = [item[1] for item in sorted_dist]

    plt.bar(x, y, color="#3498db", alpha=0.7, edgecolor="#2980b9", linewidth=1)
    plt.title(
        "Распределение количества вопросов на пользователя",
        fontsize=16,
        fontweight="bold",
        pad=20,
    )
    plt.xlabel("Количество вопросов", fontsize=12)
    plt.ylabel("Количество пользователей", fontsize=12)
    plt.yscale("log")
    plt.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"График распределения вопросов сохранен: {output_path}")


def plot_questions_distribution_linear(distribution: Dict[int, int], output_path: Path):
    """Построить распределение количества вопросов на пользователя (линейная шкала)."""
    plt.figure(figsize=(14, 8))

    sorted_dist = sorted(distribution.items())
    x = [item[0] for item in sorted_dist if item[0] <= 50]
    y = [item[1] for item in sorted_dist if item[0] <= 50]

    plt.bar(x, y, color="#3498db", alpha=0.7, edgecolor="#2980b9", linewidth=1)
    plt.title(
        "Распределение количества вопросов на пользователя (до 50 вопросов)",
        fontsize=16,
        fontweight="bold",
        pad=20,
    )
    plt.xlabel("Количество вопросов", fontsize=12)
    plt.ylabel("Количество пользователей", fontsize=12)
    plt.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"График распределения вопросов (линейный) сохранен: {output_path}")


def save_markdown_report(stats: Dict, distribution: Dict[int, int], output_path: Path):
    """Сохранить отчет в формате Markdown."""
    report = f"""# Статистический анализ пользовательской активности

## Основные метрики

- **Всего пользователей**: {stats["total_users"]}
- **Пользователей, задавших хотя бы один вопрос**: {stats["users_with_questions"]}
- **Всего вопросов**: {stats["total_questions"]}
- **Среднее количество вопросов на пользователя**: {stats["avg_questions_per_user"]}
- **Медиана вопросов на пользователя**: {stats["median_questions_per_user"]}
- **Минимум вопросов на пользователя**: {stats["min_questions_per_user"]}
- **Максимум вопросов на пользователя**: {stats["max_questions_per_user"]}

## Распределение количества вопросов на пользователя

| Количество вопросов | Количество пользователей |
|-------------------|------------------------|
"""
    for q_count, user_count in sorted(distribution.items())[:50]:
        report += f"| {q_count} | {user_count} |\n"

    report += (
        f"\n*Всего уникальных значений количества вопросов: {len(distribution)}*\n"
    )

    report += f"""
## Анализ активности

- **Процент пользователей, задавших вопросы**: {(stats["users_with_questions"] / stats["total_users"] * 100):.2f}%
- **Среднее количество вопросов на активного пользователя**: {(stats["total_questions"] / stats["users_with_questions"]):.2f}

## Графики

1. Рост пользователей по платформам: `platforms_growth.png`
2. Распределение вопросов (логарифмическая шкала): `questions_distribution_log.png`
3. Распределение вопросов (линейная шкала, до 50 вопросов): `questions_distribution_linear.png`
"""

    output_path.write_text(report, encoding="utf-8")
    print(f"Отчет в формате Markdown сохранен: {output_path}")


def save_json_report(stats: Dict, distribution: Dict[int, int], output_path: Path):
    """Сохранить отчет в формате JSON."""
    from decimal import Decimal

    def convert_decimal(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return obj

    report = {
        "generated_at": datetime.now().isoformat(),
        "statistics": {k: convert_decimal(v) for k, v in stats.items()},
        "questions_distribution": [
            {"questions": q, "users": u} for q, u in sorted(distribution.items())
        ],
    }

    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Отчет в формате JSON сохранен: {output_path}")


def main():
    """Главная функция."""
    output_dir = Path(
        "/Users/masha/src/github.com/webmasha/voproshalych-personal/2026_benchmarks/2026_analysis/statisticheskiy-analiz-pol'zovatel'skoy-aktivnosti"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    conn = get_db_connection()

    try:
        print("Получение статистики по пользователям...")
        stats = get_user_statistics(conn)
        print(f"Всего пользователей: {stats['total_users']}")
        print(f"Пользователей с вопросами: {stats['users_with_questions']}")
        print(f"Всего вопросов: {stats['total_questions']}")

        print("\nПолучение данных по платформам...")
        platforms_data = get_platforms_over_time(conn)
        print(
            f"VK пользователей: {len([d for data in platforms_data['vk'] for d in [data]])}"
        )
        print(
            f"Telegram пользователей: {len([d for data in platforms_data['telegram'] for d in [data]])}"
        )
        print(
            f"Unknown пользователей: {len([d for data in platforms_data['unknown'] for d in [data]])}"
        )

        print("\nПолучение распределения вопросов...")
        distribution = get_questions_per_user_distribution(conn)
        print(f"Уникальных значений количества вопросов: {len(distribution)}")

        print("\nПостроение графиков...")
        plot_platforms_growth(
            platforms_data,
            output_dir / "platforms_growth.png",
        )
        plot_questions_distribution(
            distribution,
            output_dir / "questions_distribution_log.png",
        )
        plot_questions_distribution_linear(
            distribution,
            output_dir / "questions_distribution_linear.png",
        )

        print("\nСохранение отчетов...")
        save_markdown_report(stats, distribution, output_dir / "report.md")
        save_json_report(stats, distribution, output_dir / "report.json")

        print("\nАнализ завершен!")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
