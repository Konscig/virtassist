"""Анализ пользователей и их взаимодействия с чат-ботом."""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parent.parent))

from qa.config import Config
from qa.database import QuestionAnswer, User, create_engine

logger = logging.getLogger(__name__)


def analyze_users_domain(engine: Engine, limit: int = 5000) -> dict[str, Any]:
    """Анализ пользователей и их взаимодействия с чат-ботом."""
    with Session(engine) as session:
        all_users = session.scalars(select(User)).all()
        total_users = len(all_users)

        user_ids_with_questions = set(
            session.scalars(select(QuestionAnswer.user_id).distinct()).all()
        )
        users_with_questions = len(user_ids_with_questions)
        users_without_questions = total_users - users_with_questions

        total_questions_real = (
            session.scalar(
                select(func.count(QuestionAnswer.id)).where(
                    QuestionAnswer.question.isnot(None)
                )
            )
            or 0
        )

        all_questions = session.scalars(
            select(QuestionAnswer)
            .where(QuestionAnswer.question.isnot(None))
            .limit(limit)
        ).all()
        total_questions = len(all_questions)

        questions_by_user = Counter(qa.user_id for qa in all_questions)
        questions_per_user_dist = {}
        max_questions = max(questions_by_user.values()) if questions_by_user else 0
        for count in range(1, max_questions + 1):
            questions_per_user_dist[str(count)] = sum(
                1 for c in questions_by_user.values() if c == count
            )

        avg_questions_per_user = (
            sum(questions_by_user.values()) / len(questions_by_user)
            if questions_by_user
            else 0.0
        )

        users_with_unanswered = set()
        users_with_answered = set()
        for qa in all_questions:
            if qa.answer and qa.answer.strip():
                users_with_answered.add(qa.user_id)
            else:
                users_with_unanswered.add(qa.user_id)

        users_with_unanswered_count = len(users_with_unanswered)
        users_with_only_unanswered = users_with_unanswered - users_with_answered

        users_by_platform = {"vk": 0, "telegram": 0, "max": 0, "unknown": 0}
        for user in all_users:
            if user.vk_id:
                users_by_platform["vk"] += 1
            elif user.telegram_id:
                users_by_platform["telegram"] += 1
            else:
                users_by_platform["unknown"] += 1

        first_date = (
            session.query(func.min(QuestionAnswer.created_at)).scalar()
            or datetime.now()
        )
        last_date = (
            session.query(func.max(QuestionAnswer.created_at)).scalar()
            or datetime.now()
        )

        questions_timeline = []
        days_range = (last_date - first_date).days + 1
        days_to_process = days_range

        user_platform_cache = {}

        for i in range(days_to_process):
            day = first_date + timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)

            day_questions = session.scalars(
                select(QuestionAnswer.id).where(
                    QuestionAnswer.created_at >= day_start,
                    QuestionAnswer.created_at <= day_end,
                )
            ).all()

            unique_users_day = set()
            vk_count = 0
            tg_count = 0
            for qid in day_questions:
                qa = session.get(QuestionAnswer, qid)
                if qa:
                    unique_users_day.add(qa.user_id)

                    if qa.user_id not in user_platform_cache:
                        user = session.get(User, qa.user_id)
                        if user:
                            if user.vk_id:
                                user_platform_cache[qa.user_id] = "vk"
                            elif user.telegram_id:
                                user_platform_cache[qa.user_id] = "telegram"
                            else:
                                user_platform_cache[qa.user_id] = "unknown"
                        else:
                            user_platform_cache[qa.user_id] = "unknown"

                    platform = user_platform_cache.get(qa.user_id, "unknown")
                    if platform == "vk":
                        vk_count += 1
                    elif platform == "telegram":
                        tg_count += 1

            questions_timeline.append(
                {
                    "date": day_start.strftime("%Y-%m-%d"),
                    "questions_count": len(day_questions),
                    "unique_users": len(unique_users_day),
                    "vk_questions": vk_count,
                    "telegram_questions": tg_count,
                }
            )

    return {
        "total_users": total_users,
        "users_with_questions": users_with_questions,
        "users_without_questions": users_without_questions,
        "users_without_questions_rate": (
            users_without_questions / total_users if total_users else 0.0
        ),
        "users_with_unanswered": users_with_unanswered_count,
        "users_with_unanswered_rate": (
            users_with_unanswered_count / users_with_questions
            if users_with_questions
            else 0.0
        ),
        "users_with_only_unanswered": len(users_with_only_unanswered),
        "total_questions": total_questions_real,
        "total_questions_analyzed": total_questions,
        "avg_questions_per_user": avg_questions_per_user,
        "questions_per_user_distribution": questions_per_user_dist,
        "users_by_platform": users_by_platform,
        "questions_timeline": questions_timeline,
        "period_days": days_to_process,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Анализ пользователей и их взаимодействия с чат-ботом"
    )
    parser.add_argument("--limit", type=int, default=5000, help="Лимит вопросов")
    parser.add_argument(
        "--output",
        type=str,
        default="benchmarks/reports/users_domain_analysis.json",
        help="Путь для JSON отчёта",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    result = analyze_users_domain(engine, limit=args.limit)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Сохранён анализ пользователей: %s", output_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
