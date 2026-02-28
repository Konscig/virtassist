"""Автоматическая аннотация датасета с помощью LLM.

Запускает LLM судью для автоматической разметки вопросов/ответов.
Использует те же настройки что и llm_judge: BENCHMARKS_JUDGE_*
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ANNOTATION_FIELDS = [
    "answer_type",
    "has_source",
    "url_relevance",
    "answer_url_relevance",
    "is_small_talk",
]

SYSTEM_PROMPT = """Ты — эксперт по аннотации данных для RAG-системы. Твоя задача — проанализировать вопрос пользователя и ответ бота, затем проставить аннотацию.

Для каждого вопроса нужно заполнить следующие поля:

1. answer_type — тип ответа:
   - 1 (Пустой) — поле answer пустое
   - 2 (Нет ответа/некорректный) — бот ответил, но ответ неполный, некорректный или бесполезный
   - 3 (Нормальный) — бот дал полезный развёрнутый ответ

2. has_source — наличие источника:
   - 0 — источника нет (проверь поле confluence_url или наличие ссылок в тексте ответа)
   - 1 — источник есть (ссылка в confluence_url или в тексте ответа)

3. url_relevance — релевантность URL вопросу:
   - 0 — по умолчанию

4. answer_url_relevance — релевантность ответа URL:
   - 0 — по умолчанию

5. is_small_talk — тип вопроса:
   - 0 (По делу) — конкретный вопрос по существу
   - 1 (Small talk) — привет, пока, как дела и т.п.
   - 2 (Про Вопрошалыча) — вопросы о системе (кто ты, что умеешь)

ВАЖНО:
- Если ответ хоть немного полезен и отвечает на вопрос — это 3 (нормальный)
- Если ответ бесполезен, не отвечает на вопрос, или просто "извините не нашёл" — это 2
- Если answer пустое — это 1
- Источник может быть в confluence_url ИЛИ в тексте ответа (ссылки вида https://...)

Верни JSON с проставленными полями."""


USER_PROMPT = """Вопрос пользователя:
{question}

Ответ бота:
{answer}

Ссылка на источник:
{confluence_url}

Проаннотируй этот вопрос и ответ. Верни JSON с полями:
- answer_type (1, 2 или 3)
- has_source (0 или 1)
- url_relevance (0)
- answer_url_relevance (0)
- is_small_talk (0, 1 или 2)

Пример ответа:
{{"answer_type": "3", "has_source": "1", "url_relevance": "0", "answer_url_relevance": "0", "is_small_talk": "0"}}"""


def get_client():
    """Создать OpenAI-совместимый клиент."""
    api_key = os.getenv("BENCHMARKS_JUDGE_API_KEY")
    base_url = os.getenv("BENCHMARKS_JUDGE_BASE_URL", "https://api.deepseek.com")

    if not api_key:
        raise ValueError("Не задан ключ API. Укажите BENCHMARKS_JUDGE_API_KEY")

    from openai import OpenAI

    return OpenAI(api_key=api_key, base_url=base_url)


def get_model() -> str:
    """Получить название модели."""
    return os.getenv("BENCHMARKS_JUDGE_MODEL", "deepseek-chat")


def call_llm(
    client, model: str, question: str, answer: str, confluence_url: str
) -> dict | None:
    """Вызвать LLM для аннотации."""
    user_text = USER_PROMPT.format(
        question=question[:1000],
        answer=answer[:2000] if answer else "(пусто)",
        confluence_url=confluence_url if confluence_url else "(нет)",
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        return json.loads(content)

    except Exception as e:
        logger.warning(f"Error calling LLM: {e}")
        return None


def has_url_in_text(text: str) -> bool:
    """Проверить, есть ли URL в тексте."""
    if not text:
        return False
    return "http://" in text.lower() or "https://" in text.lower()


def auto_annotate_dataset(
    input_path: Path,
    output_path: Path,
    batch_size: int = 10,
    delay: float = 0.5,
) -> dict[str, Any]:
    """Автоматически аннотировать датасет с помощью LLM."""
    client = get_client()
    model = get_model()

    with open(input_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    total = len(items)
    annotated = 0
    errors = 0

    for i, item in enumerate(items):
        question = item.get("question", "")
        answer = item.get("answer", "")
        confluence_url = item.get("confluence_url", "")

        if not question:
            continue

        result = call_llm(client, model, question, answer, confluence_url)

        if result:
            item["annotate_answer_type"] = result.get("answer_type", "2")
            item["annotate_has_source"] = result.get("has_source", "0")
            item["annotate_url_relevance"] = result.get("url_relevance", "0")
            item["annotate_answer_url_relevance"] = result.get(
                "answer_url_relevance", "0"
            )
            item["annotate_is_small_talk"] = result.get("is_small_talk", "0")
            annotated += 1
        else:
            errors += 1

        if (i + 1) % batch_size == 0:
            logger.info(f"Processed {i + 1}/{total} questions")

        time.sleep(delay)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "total": total,
        "annotated": annotated,
        "errors": errors,
        "output_path": str(output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Автоматическая аннотация датасета с помощью LLM"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Путь к входному JSON файлу",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Путь к выходному JSON файлу",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Логировать каждые N вопросов",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Задержка между запросами (сек)",
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

    if args.output is None:
        stem = input_path.stem
        args.output = f"{input_path.parent}/{stem}_annotated.json"

    result = auto_annotate_dataset(
        input_path=input_path,
        output_path=Path(args.output),
        batch_size=args.batch_size,
        delay=args.delay,
    )

    print(f"\nАннотация завершена:")
    print(f"  Всего вопросов: {result['total']}")
    print(f"  Проаннотировано: {result['annotated']}")
    print(f"  Ошибок: {result['errors']}")
    print(f"  Файл: {result['output_path']}")


if __name__ == "__main__":
    main()
