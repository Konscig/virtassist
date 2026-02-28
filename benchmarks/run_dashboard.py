#!/usr/bin/env python3
"""Скрипт для запуска дашборда бенчарков.

Использование:
    python benchmarks/run_dashboard.py
"""

import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

current_dir = Path(__file__).parent
project_root = current_dir.parent
reports_dir = current_dir / "reports"
sys.path.insert(0, str(project_root))


def run_user_analysis():
    """Запустить анализ пользователей, если данных нет."""
    users_data_path = reports_dir / "users_domain_analysis.json"

    if users_data_path.exists():
        logger.info("Данные пользователей уже существуют: %s", users_data_path)
        return

    logger.info("Запуск анализа пользователей...")

    try:
        from benchmarks.analyze_users_domain import analyze_users_domain
        from qa.config import Config
        from qa.database import create_engine

        engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
        result = analyze_users_domain(engine, limit=5000)

        reports_dir.mkdir(parents=True, exist_ok=True)
        users_data_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Сохранён анализ пользователей: %s", users_data_path)

    except Exception as e:
        logger.warning("Не удалось запустить анализ пользователей: %s", e)


try:
    from benchmarks.dashboard import main

    if __name__ == "__main__":
        run_user_analysis()
        main()
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print(
        "Убедитесь, что вы запускаете этот скрипт из директории Submodules/voproshalych"
    )
    print("Или запустите напрямую: python benchmarks/dashboard.py")
    sys.exit(1)
