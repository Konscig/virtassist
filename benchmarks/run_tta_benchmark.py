"""CLI скрипт для запуска TTA (Time To Answer) бенчмарков.

Использование:
    python run_tta_benchmark.py --mode e2e --limit 50
    python run_tta_benchmark.py --mode component --limit 100
    python run_tta_benchmark.py --mode all --limit 50
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from qa.config import Config
from qa.database import create_engine, Chunk, QuestionAnswer
from benchmarks.models.tta_benchmark import TTABenchmark
from benchmarks.tta_dataset_generator import (
    generate_tta_dataset_from_real_questions,
    generate_tta_dataset_with_chunks,
    save_tta_dataset,
    load_tta_dataset,
    generate_tta_dataset_stratified,
    generate_tta_dataset_with_scenarios,
)
from sentence_transformers import SentenceTransformer
from sqlalchemy import select, func, func

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=".env.docker")
load_dotenv(dotenv_path=".env", override=False)


def parse_arguments():
    """Разобрать аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description="Запуск TTA (Time To Answer) бенчмарков"
    )
    parser.add_argument(
        "--mode",
        choices=["e2e", "component", "all"],
        default="e2e",
        help="Режим бенчмарка (default: e2e)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Количество вопросов для тестирования (default: 50)",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        help="Путь к существующему датасету JSON",
    )
    parser.add_argument(
        "--dataset-type",
        choices=["simple", "with-chunks", "stratified", "scenarios"],
        default="simple",
        help="Тип генерируемого датасета (default: simple)",
    )
    parser.add_argument(
        "--cache-ratio",
        type=float,
        default=0.3,
        help="Доля вопросов из кэша для stratified датасета (default: 0.3)",
    )
    parser.add_argument(
        "--limit-per-scenario",
        type=int,
        default=10,
        help="Количество вопросов на каждый сценарий (default: 10)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="benchmarks/reports",
        help="Директория для сохранения результатов (default: benchmarks/reports)",
    )
    parser.add_argument(
        "--save-dataset",
        action="store_true",
        help="Сохранить сгенерированный датасет",
    )
    parser.add_argument(
        "--save-per-record",
        action="store_true",
        help="Сохранить датасет с метриками для каждой записи",
    )
    parser.add_argument(
        "--test-user-id",
        type=int,
        default=1,
        help="ID тестового пользователя (default: 1)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Подробное логирование",
    )

    return parser.parse_args()


def check_prerequisites(engine) -> bool:
    """Проверить предварительные условия.

    Args:
        engine: Движок базы данных

    Returns:
        True если все условия выполнены
    """
    logger.info("Проверка предварительных условий...")

    with engine.connect() as conn:
        chunk_count = conn.scalar(select(func.count(Chunk.id)))
        qa_count = conn.scalar(select(func.count(QuestionAnswer.id)))

    logger.info(f"Чанков в БД: {chunk_count}")
    logger.info(f"Вопросов в БД: {qa_count}")

    if chunk_count == 0:
        logger.error(
            "❌ Нет чанков в БД! Запустите: python benchmarks/load_database_dump.py"
        )
        return False

    if qa_count == 0:
        logger.error("❌ Нет вопросов в БД! Загрузите дамп БД.")
        return False

    logger.info("✅ Предварительные условия выполнены")
    return True


def load_encoder() -> SentenceTransformer:
    """Загрузить модель эмбеддингов.

    Returns:
        Модель эмбеддингов
    """
    embedding_model_path = os.getenv(
        "EMBEDDING_MODEL_PATH", "models/ru_sentence_transformer"
    )

    logger.info(f"Загрузка модели эмбеддингов: {embedding_model_path}")
    encoder = SentenceTransformer(embedding_model_path, device="cpu")
    logger.info("✅ Модель эмбеддингов загружена")

    return encoder


def get_or_generate_dataset(
    engine,
    args,
) -> List[Dict[str, Any]]:
    """Получить или сгенерировать датасет.

    Args:
        engine: Движок базы данных
        args: Аргументы командной строки

    Returns:
        Список вопросов датасета
    """
    if args.dataset:
        logger.info(f"Загрузка датасета из {args.dataset}")
        return load_tta_dataset(args.dataset)

    logger.info(f"Генерация датасета (type={args.dataset_type}, limit={args.limit})")

    if args.dataset_type == "simple":
        dataset = generate_tta_dataset_from_real_questions(
            engine,
            limit=args.limit,
            require_answer=True,
        )
    elif args.dataset_type == "with-chunks":
        dataset = generate_tta_dataset_with_chunks(
            engine,
            limit=args.limit,
        )
    elif args.dataset_type == "stratified":
        dataset = generate_tta_dataset_stratified(
            engine,
            limit=args.limit,
            cache_ratio=args.cache_ratio,
        )
    elif args.dataset_type == "scenarios":
        dataset = generate_tta_dataset_with_scenarios(
            engine,
            limit_per_scenario=args.limit_per_scenario,
        )
    else:
        raise ValueError(f"Неизвестный тип датасета: {args.dataset_type}")

    if args.save_dataset:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"benchmarks/data/tta_dataset_{timestamp}.json"
        save_tta_dataset(dataset, output_path)
        logger.info(f"✅ Датасет сохранен в {output_path}")

    return dataset


def run_e2e_benchmark(
    benchmark: TTABenchmark,
    dataset: List[Dict[str, Any]],
    test_user_id: int,
) -> Dict[str, float]:
    """Запустить E2E бенчмарк.

    Args:
        benchmark: Экземпляр TTABenchmark
        dataset: Датасет вопросов
        test_user_id: ID тестового пользователя

    Returns:
        Словарь с метриками
    """
    logger.info("=" * 60)
    logger.info("Запуск E2E (End-to-End) бенчмарка")
    logger.info("=" * 60)

    metrics = benchmark.run_e2e_benchmark(dataset, test_user_id=test_user_id)

    return metrics


def run_component_benchmark(
    benchmark: TTABenchmark,
    dataset: List[Dict[str, Any]],
    test_user_id: int,
) -> Dict[str, float]:
    """Запустить компонентный бенчмарк.

    Args:
        benchmark: Экземпляр TTABenchmark
        dataset: Датасет вопросов
        test_user_id: ID тестового пользователя

    Returns:
        Словарь с метриками
    """
    logger.info("=" * 60)
    logger.info("Запуск компонентного бенчмарка")
    logger.info("=" * 60)

    metrics = benchmark.run_component_benchmark(dataset, test_user_id=test_user_id)

    return metrics


def print_metrics(metrics: Dict[str, float], title: str = "Метрики"):
    """Вывести метрики в консоль.

    Args:
        metrics: Словарь с метриками
        title: Заголовок
    """
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")

    for key, value in sorted(metrics.items()):
        if isinstance(value, float):
            if "Rate" in key or "Ratio" in key:
                print(f"  {key}: {value:.2%}")
            elif "P" in key or "mean" in key or "std" in key:
                print(f"  {key}: {value:.2f}ms")
            else:
                print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")

    print(f"{'=' * 60}\n")


def save_metrics(
    metrics: Dict[str, Any],
    dataset: List[Dict[str, Any]],
    output_dir: str,
    mode: str,
    save_per_record: bool = False,
) -> str:
    """Сохранить метрики в JSON файл.

    Args:
        metrics: Словарь с метриками
        dataset: Датасет с метриками для каждой записи
        output_dir: Директория для сохранения
        mode: Режим бенчмарка
        save_per_record: Сохранить ли датасет с метриками для каждой записи

    Returns:
        Путь к сохраненному файлу
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"{output_dir}/tta_benchmark_{mode}_{timestamp}.json"

    report = {
        "timestamp": timestamp,
        "mode": mode,
        "metrics": metrics,
    }

    if save_per_record:
        per_record_path = (
            f"{output_dir}/tta_benchmark_{mode}_{timestamp}_per_record.json"
        )
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        with open(per_record_path, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)

        report["per_record_dataset"] = per_record_path
        logger.info(f"✅ Датасет с метриками сохранен в {per_record_path}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ Результаты сохранены в {output_path}")
    return output_path


def main():
    """Главная функция."""
    args = parse_arguments()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)

    if not check_prerequisites(engine):
        sys.exit(1)

    encoder = load_encoder()

    benchmark = TTABenchmark(engine, encoder)

    dataset = get_or_generate_dataset(engine, args)

    if not dataset:
        logger.error("❌ Датасет пуст!")
        sys.exit(1)

    logger.info(f"✅ Датасет загружен: {len(dataset)} вопросов")

    all_metrics = {}

    if args.mode in ["e2e", "all"]:
        e2e_metrics = run_e2e_benchmark(benchmark, dataset, args.test_user_id)
        all_metrics["e2e"] = e2e_metrics
        print_metrics(e2e_metrics, "E2E (End-to-End) метрики")

    if args.mode in ["component", "all"]:
        component_metrics = run_component_benchmark(
            benchmark, dataset, args.test_user_id
        )
        all_metrics["component"] = component_metrics
        print_metrics(component_metrics, "Компонентные метрики")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = save_metrics(
        all_metrics, dataset, args.output_dir, args.mode, args.save_per_record
    )

    logger.info("✅ TTA бенчмарк завершен успешно!")

    if __name__ == "__main__":
        main()
