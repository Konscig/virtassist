"""Простой тест для проверки импортов."""

import sys

print("Python executable:", sys.executable)
print("Python version:", sys.version)

try:
    from sqlalchemy import select, func

    print("✅ SQLAlchemy импортирован")
except ImportError as e:
    print(f"❌ SQLAlchemy ошибка: {e}")

try:
    from qa.config import Config

    print("✅ Config импортирован")
except ImportError as e:
    print(f"❌ Config ошибка: {e}")

try:
    from benchmarks.models.tta_benchmark import TTABenchmark

    print("✅ TTABenchmark импортирован")
except ImportError as e:
    print(f"❌ TTABenchmark ошибка: {e}")
