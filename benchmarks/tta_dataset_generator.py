"""Генератор тестовых датасетов для TTA бенчмарков из реальных вопросов."""

import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import Engine, select, func
from sqlalchemy.orm import Session

try:
    from qa.database import Chunk, QuestionAnswer
except ImportError:
    from database import Chunk, QuestionAnswer

logger = logging.getLogger(__name__)


def generate_tta_dataset_from_real_questions(
    engine: Engine,
    limit: int = 100,
    min_length: int = 10,
    max_length: int = 500,
    require_answer: bool = True,
    random_seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Сгенерировать датасет для TTA бенчмарка из реальных вопросов.

    Извлекает вопросы из таблицы question_answer реальной БД и формирует
    датасет для измерения Time To Answer.

    Args:
        engine: Движок базы данных
        limit: Максимальное количество вопросов в датасете
        min_length: Минимальная длина вопроса (символы)
        max_length: Максимальная длина вопроса (символы)
        require_answer: Требовать наличия ответа на вопрос
        random_seed: Seed для воспроизводимости

    Returns:
        Список записей датасета [{"question": "...", "ground_truth_answer": "...", ...}]
    """
    if random_seed is not None:
        random.seed(random_seed)

    logger.info(f"Генерация TTA датасета из реальных вопросов (limit={limit})")

    with Session(engine) as session:
        query = select(QuestionAnswer)

        if require_answer:
            query = query.where(QuestionAnswer.answer.isnot(None))

        question_answers = session.scalars(query).all()

        if not question_answers:
            logger.warning("Не найдено вопросов в базе данных")
            return []

        logger.info(f"Всего найдено вопросов: {len(question_answers)}")

        dataset = []

        for qa in question_answers:
            question = qa.question

            if not question or len(question) < min_length:
                continue

            if len(question) > max_length:
                continue

            record = {
                "id": qa.id,
                "question": question,
                "ground_truth_answer": qa.answer if qa.answer else "",
                "confluence_url": qa.confluence_url,
                "score": qa.score,
                "user_id": qa.user_id,
                "created_at": qa.created_at.isoformat() if qa.created_at else None,
            }

            dataset.append(record)

            if len(dataset) >= limit:
                break

    logger.info(f"Сгенерирован датасет с {len(dataset)} вопросами")
    return dataset


def generate_tta_dataset_with_chunks(
    engine: Engine,
    limit: int = 50,
    random_seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Сгенерировать датасет с информацией о чанках.

    Создает датасет, где для каждого вопроса известен релевантный чанк.

    Args:
        engine: Движок базы данных
        limit: Максимальное количество вопросов в датасете
        random_seed: Seed для воспроизводимости

    Returns:
        Список записей с информацией о чанках
    """
    if random_seed is not None:
        random.seed(random_seed)

    logger.info(f"Генерация TTA датасета с чанками (limit={limit})")

    with Session(engine) as session:
        questions_with_urls = session.scalars(
            select(QuestionAnswer)
            .where(QuestionAnswer.confluence_url.isnot(None))
            .where(QuestionAnswer.confluence_url != "")
            .where(QuestionAnswer.answer.isnot(None))
        ).all()

        if not questions_with_urls:
            logger.warning("Не найдено вопросов с URL чанков")
            return []

        dataset = []

        for qa in questions_with_urls:
            chunks = session.scalars(
                select(Chunk).where(Chunk.confluence_url == qa.confluence_url).limit(1)
            ).all()

            if not chunks:
                continue

            chunk = chunks[0]

            record = {
                "id": qa.id,
                "question": qa.question,
                "ground_truth_answer": qa.answer,
                "confluence_url": qa.confluence_url,
                "chunk_id": chunk.id,
                "chunk_text": chunk.text,
                "user_id": qa.user_id,
                "created_at": qa.created_at.isoformat() if qa.created_at else None,
            }

            dataset.append(record)

            if len(dataset) >= limit:
                break

    logger.info(f"Сгенерирован датасет с {len(dataset)} вопросами и чанками")
    return dataset


def save_tta_dataset(
    dataset: List[Dict[str, Any]],
    output_path: str,
) -> None:
    """Сохранить датасет в JSON файл.

    Args:
        dataset: Список записей датасета
        output_path: Путь к выходному файлу
    """
    import json

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    logger.info(f"Датасет сохранен в {output_path}")


def load_tta_dataset(input_path: str) -> List[Dict[str, Any]]:
    """Загрузить датасет из JSON файла.

    Args:
        input_path: Путь к файлу

    Returns:
        Список записей датасета
    """
    import json

    with open(input_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    logger.info(f"Загружен датасет с {len(dataset)} записями из {input_path}")
    return dataset


def generate_tta_dataset_stratified(
    engine: Engine,
    limit: int = 100,
    cache_ratio: float = 0.3,
    random_seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Сгенерировать стратифицированный датасет.

    Создает датасет с заданной пропорцией вопросов, которые должны попасть в кэш.

    Args:
        engine: Движок базы данных
        limit: Общее количество вопросов
        cache_ratio: Доля вопросов из кэша (0.0 - 1.0)
        random_seed: Seed для воспроизводимости

    Returns:
        Список записей датасета
    """
    if random_seed is not None:
        random.seed(random_seed)

    logger.info(
        f"Генерация стратифицированного TTA датасета "
        f"(limit={limit}, cache_ratio={cache_ratio})"
    )

    cache_count = int(limit * cache_ratio)
    no_cache_count = limit - cache_count

    with Session(engine) as session:
        high_score_questions = session.scalars(
            select(QuestionAnswer)
            .where(QuestionAnswer.score == 5)
            .where(QuestionAnswer.answer.isnot(None))
            .limit(cache_count * 2)
        ).all()

        random.shuffle(high_score_questions)
        cache_questions = high_score_questions[:cache_count]

        low_score_questions = session.scalars(
            select(QuestionAnswer)
            .where(QuestionAnswer.score.isnot(None))
            .where(QuestionAnswer.score < 5)
            .where(QuestionAnswer.answer.isnot(None))
            .limit(no_cache_count * 2)
        ).all()

        random.shuffle(low_score_questions)
        no_cache_questions = low_score_questions[:no_cache_count]

        dataset = []

        for qa in cache_questions:
            dataset.append(
                {
                    "id": qa.id,
                    "question": qa.question,
                    "ground_truth_answer": qa.answer,
                    "confluence_url": qa.confluence_url,
                    "score": qa.score,
                    "user_id": qa.user_id,
                    "expected_cache_hit": True,
                    "created_at": qa.created_at.isoformat() if qa.created_at else None,
                }
            )

        for qa in no_cache_questions:
            dataset.append(
                {
                    "id": qa.id,
                    "question": qa.question,
                    "ground_truth_answer": qa.answer,
                    "confluence_url": qa.confluence_url,
                    "score": qa.score,
                    "user_id": qa.user_id,
                    "expected_cache_hit": False,
                    "created_at": qa.created_at.isoformat() if qa.created_at else None,
                }
            )

        random.shuffle(dataset)

    logger.info(
        f"Сгенерирован стратифицированный датасет: "
        f"{len(cache_questions)} cache hits, {len(no_cache_questions)} no cache"
    )
    return dataset


def generate_tta_dataset_with_scenarios(
    engine: Engine,
    limit_per_scenario: int = 25,
    random_seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Сгенерировать датасет с разделением по 4 сценариям обработки.

    Сценарии:
    1. cache_hit: кэш-хит (score=5, длина 10-100)
    2. generation: генерация (score=4 или None, длина 50-200, есть URL чанка)
    3. chunk_not_found: чанк не найден (длина >300, редкие слова)
    4. template: шаблонный ответ (score < 3, короткие <20)

    Args:
        engine: Движок базы данных
        limit_per_scenario: Количество вопросов на каждый сценарий
        random_seed: Seed для воспроизводимости

    Returns:
        Список записей с полями:
        - question
        - expected_scenario
        - ground_truth_answer
        - confluence_url
        - score
        - user_id
        - created_at
    """
    if random_seed is not None:
        random.seed(random_seed)

    logger.info(
        f"Генерация датасета по сценариям (limit_per_scenario={limit_per_scenario})"
    )

    with Session(engine) as session:
        # Сценарий 1: cache_hit (score=5, длина 10-100)
        cache_hit_questions = list(
            session.scalars(
                select(QuestionAnswer)
                .where(QuestionAnswer.score == 5)
                .where(QuestionAnswer.answer.isnot(None))
                .limit(limit_per_scenario * 2)
            ).all()
        )

        random.shuffle(cache_hit_questions)
        cache_hit_dataset = []

        for qa in cache_hit_questions[:limit_per_scenario]:
            question = qa.question
            if not question or len(question) < 10 or len(question) > 100:
                continue

            cache_hit_dataset.append(
                {
                    "id": qa.id,
                    "question": question,
                    "ground_truth_answer": qa.answer,
                    "confluence_url": qa.confluence_url,
                    "score": qa.score,
                    "user_id": qa.user_id,
                    "expected_scenario": "cache_hit",
                    "created_at": qa.created_at.isoformat() if qa.created_at else None,
                }
            )

        # Сценарий 2: generation (score=4 или None, длина 50-200, есть URL чанка)
        generation_questions = list(
            session.scalars(
                select(QuestionAnswer)
                .where((QuestionAnswer.score == 4) | (QuestionAnswer.score.is_(None)))
                .where(QuestionAnswer.confluence_url.isnot(None))
                .where(QuestionAnswer.confluence_url != "")
                .where(QuestionAnswer.answer.isnot(None))
                .limit(limit_per_scenario * 2)
            ).all()
        )

        random.shuffle(generation_questions)
        generation_dataset = []

        for qa in generation_questions[:limit_per_scenario]:
            question = qa.question
            if not question or len(question) < 50 or len(question) > 200:
                continue

            generation_dataset.append(
                {
                    "id": qa.id,
                    "question": question,
                    "ground_truth_answer": qa.answer,
                    "confluence_url": qa.confluence_url,
                    "score": qa.score,
                    "user_id": qa.user_id,
                    "expected_scenario": "generation",
                    "created_at": qa.created_at.isoformat() if qa.created_at else None,
                }
            )

        # Сценарий 3: chunk_not_found (длина >300, редкие слова)
        chunk_not_found_questions = list(
            session.scalars(
                select(QuestionAnswer)
                .where(QuestionAnswer.answer.isnot(None))
                .where(func.length(QuestionAnswer.question) > 300)
                .limit(limit_per_scenario * 2)
            ).all()
        )

        random.shuffle(chunk_not_found_questions)
        chunk_not_found_dataset = []

        for qa in chunk_not_found_questions[:limit_per_scenario]:
            chunk_not_found_dataset.append(
                {
                    "id": qa.id,
                    "question": qa.question,
                    "ground_truth_answer": qa.answer,
                    "confluence_url": None,  # Сначала ставим None, чтобы гарантированно не найти чанк
                    "score": qa.score,
                    "user_id": qa.user_id,
                    "expected_scenario": "chunk_not_found",
                    "created_at": qa.created_at.isoformat() if qa.created_at else None,
                }
            )

        # Сценарий 4: template (score < 3, короткие <20)
        template_questions = list(
            session.scalars(
                select(QuestionAnswer)
                .where(QuestionAnswer.score < 3)
                .where(QuestionAnswer.confluence_url.isnot(None))
                .where(QuestionAnswer.confluence_url != "")
                .where(func.length(QuestionAnswer.question) < 20)
                .limit(limit_per_scenario * 2)
            ).all()
        )

        random.shuffle(template_questions)
        template_dataset = []

        for qa in template_questions[:limit_per_scenario]:
            template_dataset.append(
                {
                    "id": qa.id,
                    "question": qa.question,
                    "ground_truth_answer": qa.answer,
                    "confluence_url": qa.confluence_url,  # Есть URL чанка
                    "score": qa.score,
                    "user_id": qa.user_id,
                    "expected_scenario": "template",
                    "created_at": qa.created_at.isoformat() if qa.created_at else None,
                }
            )

        # Сценарий 2: generation (score=4 или None, длина 50-200, есть URL чанка)
        generation_questions = session.scalars(
            select(QuestionAnswer)
            .where((QuestionAnswer.score == 4) | (QuestionAnswer.score.is_(None)))
            .where(QuestionAnswer.confluence_url.isnot(None))
            .where(QuestionAnswer.confluence_url != "")
            .where(QuestionAnswer.answer.isnot(None))
            .limit(limit_per_scenario * 2)
        ).all()

        random.shuffle(generation_questions)
        generation_dataset = []

        for qa in generation_questions[:limit_per_scenario]:
            question = qa.question
            if not question or len(question) < 50 or len(question) > 200:
                continue

            generation_dataset.append(
                {
                    "id": qa.id,
                    "question": question,
                    "ground_truth_answer": qa.answer,
                    "confluence_url": qa.confluence_url,
                    "score": qa.score,
                    "user_id": qa.user_id,
                    "expected_scenario": "generation",
                    "created_at": qa.created_at.isoformat() if qa.created_at else None,
                }
            )

        # Сценарий 3: chunk_not_found (длина >300, редкие слова)
        chunk_not_found_questions = session.scalars(
            select(QuestionAnswer)
            .where(QuestionAnswer.answer.isnot(None))
            .where(func.length(QuestionAnswer.question) > 300)
            .limit(limit_per_scenario * 2)
        ).all()

        random.shuffle(chunk_not_found_questions)
        chunk_not_found_dataset = []

        for qa in chunk_not_found_questions[:limit_per_scenario]:
            chunk_not_found_dataset.append(
                {
                    "id": qa.id,
                    "question": qa.question,
                    "ground_truth_answer": qa.answer,
                    "confluence_url": None,  # Сначала ставим None, чтобы гарантированно не найти чанк
                    "score": qa.score,
                    "user_id": qa.user_id,
                    "expected_scenario": "chunk_not_found",
                    "created_at": qa.created_at.isoformat() if qa.created_at else None,
                }
            )

        # Сценарий 4 (Template) убран по запросу — это edge case/fallback

        # Сценарий 3: chunk_not_found (длина >300, редкие слова)
        chunk_not_found_questions = list(
            session.scalars(
                select(QuestionAnswer)
                .where(QuestionAnswer.answer.isnot(None))
                .where(func.length(QuestionAnswer.question) > 300)
                .limit(limit_per_scenario * 2)
            ).all()
        )

        random.shuffle(chunk_not_found_questions)
        chunk_not_found_dataset = []

        for qa in chunk_not_found_questions[:limit_per_scenario]:
            chunk_not_found_dataset.append(
                {
                    "id": qa.id,
                    "question": qa.question,
                    "ground_truth_answer": qa.answer,
                    "confluence_url": None,
                    "score": qa.score,
                    "user_id": qa.user_id,
                    "expected_scenario": "chunk_not_found",
                    "created_at": qa.created_at.isoformat() if qa.created_at else None,
                }
            )

        # Объединить и перемешать
        dataset = (
            cache_hit_dataset
            + generation_dataset
            + chunk_not_found_dataset
            + template_dataset
        )
        random.shuffle(dataset)

    logger.info(
        f"Сгенерирован датасет по сценариям: "
        f"{len(cache_hit_dataset)} cache_hit, "
        f"{len(generation_dataset)} generation, "
        f"{len(chunk_not_found_dataset)} chunk_not_found, "
        f"{len(template_dataset)} template"
    )

    return dataset
