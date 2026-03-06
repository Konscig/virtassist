"""Аннотация датасета с помощью локальной модели Ollama.

Использует qwen3.5:9b для автоматической разметки вопросов/ответов.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime
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
   - 3 (Идеальный) — только в КРАЙНИХ случаях, когда семантика вопроса и ответа ИДЕАЛЬНО совпадают

2. has_source — наличие источника:
   - 0 — источника нет (проверь поле confluence_url или наличие ссылок в тексте ответа)
   - 1 — источник есть (ссылка в confluence_url или в тексте ответа)

3. url_relevance — релевантность URL вопросу:
   - 0 — URL не релевантен вопросу
   - 1 — URL релевантен вопросу (содержит информацию по теме вопроса)
   - Заполняется ТОЛЬКО если есть источник (has_source=1)

4. answer_url_relevance — релевантность ответа URL:
   - 0 — ответ не связан с предоставленным URL
   - 1 — ответ соответствует информации из URL
   - Заполняется ТОЛЬКО если есть источник (has_source=1)

5. is_small_talk — тип вопроса:
   - 0 (По делу) — конкретный вопрос по существу
   - 1 (Small talk) — привет, пока, как дела и т.п.
   - 2 (Про Вопрошалыча) — вопросы о системе (кто ты, что умеешь)

СТРОГИЕ ПРАВИЛА для answer_type:
- 3 (Идеальный) — используется ТОЛЬКО в редчайших случаях, когда:
  * Вопрос и ответ семантически ИДЕАЛЬНО совпадают
  * Ответ полностью раскрывает тему вопроса
  * Нет никаких сомнений в качестве ответа
- 2 используется в большинстве случаев когда есть ответ:
  * Если в ответе что-то написано — обязательно проанализируй что именно
  * Если ответ не идеальный, если есть хоть какие-то сомнения — выбирай 2
  * Если не понимаешь, является ли ответ идеальным — выбирай 2
  * "Извините, не нашёл" — это 2
  * Ответ частично неполный — это 2
  * Ответ есть, но не по существу — это 2
  * Чуть что не так — выбирай 2
- 1 — только если answer совсем пустое

ПРАВИЛА для url_relevance и answer_url_relevance:
- Если источника нет (has_source=0) — ставь 0 для обоих полей
- Если источник ЕСТЬ — нужно проанализировать:
  * url_relevance: соответствует ли URL (или его название/содержимое) теме вопроса?
  * answer_url_relevance: использует ли ответ информацию из этого URL?
- Если в вопросе есть URL в тексте ответа (не в поле confluence_url) — найди его в справочнике и определи релевантность

Верни JSON с проставленными полями."""


USER_PROMPT = """Вопрос пользователя:
{question}

Ответ бота:
{answer}

Ссылка на источник (confluence_url):
{confluence_url}

Название документа по ссылке:
{source_title}

Проаннотируй этот вопрос и ответ. Верни JSON с полями:
- answer_type (1, 2 или 3)
- has_source (0 или 1)
- url_relevance (0 или 1) - релевантен ли URL вопросу?
- answer_url_relevance (0 или 1) - использует ли ответ информацию из URL?
- is_small_talk (0, 1 или 2)

Пример ответа:
{{"answer_type": "3", "has_source": "1", "url_relevance": "1", "answer_url_relevance": "1", "is_small_talk": "0"}}"""


def call_ollama(
    question: str,
    answer: str,
    confluence_url: str,
    source_title: str,
    url_mapping: dict,
    model: str = "qwen3.5:9b",
    max_retries: int = 3,
) -> dict | None:
    """Вызвать Ollama для аннотации."""
    import ollama
    import re

    # Check if there's a URL in answer text (not in confluence_url field)
    urls_in_answer = re.findall(r"(https://[^\s<>\)]+)", answer or "")

    # Build URL context
    url_context = ""
    if confluence_url:
        url_context += f"URL из БД: {confluence_url}\n"
        if source_title:
            url_context += f"Название: {source_title}\n"

    # Add URLs found in answer text with their titles
    if urls_in_answer:
        url_context += "\nURLы найденные в тексте ответа:\n"
        for url in urls_in_answer[:3]:  # Limit to 3 URLs
            title = ""
            # Try to find title in our mapping
            if url in url_mapping:
                title = url_mapping[url].get("title", "")
            elif confluence_url and url in confluence_url:
                title = source_title
            url_context += f"- {url}\n"
            if title:
                url_context += f"  Название: {title}\n"

    user_text = USER_PROMPT.format(
        question=question[:1000],
        answer=answer[:2000] if answer else "(пусто)",
        confluence_url=confluence_url if confluence_url else "(нет)",
        source_title=source_title if source_title else "(нет)",
    )

    if url_context:
        user_text += f"\n\n{url_context}"

    for attempt in range(max_retries):
        try:
            logger.info(
                f"Calling Ollama (attempt {attempt + 1}/{max_retries}), question: {question[:100]}..."
            )
            response = ollama.chat(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                options={"temperature": 0.1},
                format="json",
                timeout=120,
            )
            logger.info(f"Ollama response received, parsing JSON...")
            content = response["message"]["content"]

            # Try to parse JSON, handle malformed responses
            try:
                result = json.loads(content)
                return result
            except json.JSONDecodeError as je:
                # Try to extract JSON from the response
                import re as re_module

                json_match = re_module.search(r"\{[^{}]*\}", content)
                if json_match:
                    try:
                        result = json.loads(json_match.group())
                        logger.info(f"Extracted JSON from malformed response")
                        return result
                    except json.JSONDecodeError:
                        pass

                logger.warning(
                    f"Error parsing JSON (attempt {attempt + 1}/{max_retries}): {je}"
                )
                logger.debug(f"Response content: {content[:500]}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return None

        except Exception as e:
            logger.warning(
                f"Error calling Ollama (attempt {attempt + 1}/{max_retries}): {e}"
            )
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return None

    return None


def has_url_in_text(text: str) -> bool:
    """Проверить, есть ли URL в тексте."""
    if not text:
        return False
    return "http://" in text.lower() or "https://" in text.lower()


def check_for_stop(output_path: Path) -> bool:
    """Проверить, не 请求 ли остановка."""
    stop_file = output_path.parent / ".stop_annotation"
    return stop_file.exists()


def request_stop(output_path: Path) -> None:
    """Запросить остановку после следующего батча."""
    stop_file = output_path.parent / ".stop_annotation"
    stop_file.write_text("")
    logger.info(f"Остановка запланирована. Файл: {stop_file}")


def set_default_annotations(item: dict) -> dict:
    """Установить значения по умолчанию на основе данных."""
    answer = item.get("answer", "") or ""
    confluence_url = item.get("confluence_url", "") or ""

    if not answer:
        item["annotate_answer_type"] = "1"
        item["annotate_answer_url_relevance"] = "0"
    else:
        item["annotate_answer_type"] = "3"

    if not confluence_url and not has_url_in_text(answer):
        item["annotate_has_source"] = "0"
        item["annotate_url_relevance"] = "0"
        item["annotate_answer_url_relevance"] = "0"
    else:
        item["annotate_has_source"] = "1"

    item["annotate_is_small_talk"] = "0"

    return item


def annotate_dataset(
    input_path: Path,
    output_path: Path,
    model: str = "qwen3.5:9b",
    batch_size: int = 10,
    delay: float = 0.5,
    skip_annotated: bool = True,
) -> dict[str, Any]:
    """Аннотировать датасет с помощью Ollama."""
    with open(input_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    # Check for existing annotated file (resume support)
    start_index = 0
    if output_path.exists():
        logger.info(f"Found existing annotated file: {output_path}")
        with open(output_path, "r", encoding="utf-8") as f:
            existing_items = json.load(f)

        # Find the last annotated item (where annotate_is_small_talk is not None)
        for i, item in enumerate(existing_items):
            if item.get("annotate_is_small_talk") is not None:
                start_index = i + 1

        # Merge existing annotations into items
        for i, item in enumerate(items):
            if i < len(existing_items):
                for field in ANNOTATION_FIELDS:
                    if existing_items[i].get(f"annotate_{field}") is not None:
                        item[f"annotate_{field}"] = existing_items[i].get(
                            f"annotate_{field}"
                        )

        logger.info(f"Resuming from index {start_index}")

    # Load URL mapping for titles
    url_mapping = {}
    url_json_path = Path(__file__).parent / "confluence_urls.json"
    try:
        with open(url_json_path, "r", encoding="utf-8") as f:
            url_mapping = json.load(f)
    except FileNotFoundError:
        logger.warning(
            f"Файл {url_json_path} не найден, названия URL не будут использованы"
        )

    total = len(items)
    annotated = 0
    errors = 0
    skipped = 0

    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save initial state if starting from scratch
    if start_index == 0:
        output_path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    for i, item in enumerate(items):
        if i < start_index:
            skipped += 1
            continue

        question = item.get("question", "")

        if not question:
            continue

        already_annotated = item.get("annotate_is_small_talk") is not None
        answer = item.get("answer", "") or ""
        confluence_url = item.get("confluence_url", "") or ""
        source_title = item.get("source_title", "") or ""

        # Try to get title from mapping if not in item
        if not source_title and confluence_url and confluence_url in url_mapping:
            source_title = url_mapping[confluence_url].get("title", "")

        if skip_annotated and already_annotated:
            skipped += 1
            continue

        set_default_annotations(item)

        logger.info(f"Processing question {i + 1}/{total} (index: {i})")
        if answer or confluence_url or has_url_in_text(answer):
            result = call_ollama(
                question,
                answer,
                confluence_url,
                source_title,
                url_mapping,
                model,
                max_retries=3,
            )

            if result:
                item["annotate_answer_type"] = result.get(
                    "answer_type", item.get("annotate_answer_type")
                )
                item["annotate_has_source"] = result.get(
                    "has_source", item.get("annotate_has_source")
                )
                item["annotate_url_relevance"] = result.get("url_relevance", "0")
                item["annotate_answer_url_relevance"] = result.get(
                    "answer_url_relevance", "0"
                )
                item["annotate_is_small_talk"] = result.get("is_small_talk", "0")
                annotated += 1
            else:
                errors += 1
        else:
            annotated += 1

        # Save every batch_size questions
        if (i + 1) % batch_size == 0:
            logger.info(f"Processed {i + 1}/{total} questions")
            output_path.write_text(
                json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            logger.info(f"Saved progress to {output_path}")

            # Check for soft stop request
            if check_for_stop(output_path):
                logger.info(
                    "Получен запрос на остановку. Сохраняем прогресс и выходим."
                )
                stop_file = output_path.parent / ".stop_annotation"
                if stop_file.exists():
                    stop_file.unlink()
                break

        time.sleep(delay)

    # Final save
    output_path.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "total": total,
        "annotated": annotated,
        "skipped": skipped,
        "errors": errors,
        "output_path": str(output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Аннотация датасета с помощью локальной модели Ollama"
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
        "--model",
        type=str,
        default="qwen3.5:9b",
        help="Модель Ollama (по умолчанию qwen3.5:9b)",
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
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Не пропускать уже аннотированные записи",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Запросить мягкую остановку (после следующего батча)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Показать статус текущей аннотации",
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
        args.output = f"{input_path.parent}/{input_path.stem}_annotated.json"

    output_path = Path(args.output)

    # Handle --status
    if args.status:
        if not output_path.exists():
            print("Аннотация еще не начата.")
            return
        with open(output_path, "r", encoding="utf-8") as f:
            items = json.load(f)
        total = len(items)
        annotated = sum(
            1 for item in items if item.get("annotate_is_small_talk") is not None
        )
        print(f"Статус аннотации:")
        print(f"  Всего вопросов: {total}")
        print(f"  Проаннотировано: {annotated}")
        print(f"  Осталось: {total - annotated}")
        print(f"  Прогресс: {annotated * 100 / total:.1f}%")
        print(f"  Файл: {output_path}")
        return

    # Handle --stop
    if args.stop:
        stop_file = output_path.parent / ".stop_annotation"
        if stop_file.exists():
            print("Остановка уже запланирована.")
        else:
            request_stop(output_path)
            print(f"Запрос на остановку создан: {stop_file}")
            print("Аннотация остановится после следующего батча (10 вопросов).")
        return

    logger.info(f"Using model: {args.model}")

    result = annotate_dataset(
        input_path=input_path,
        output_path=output_path,
        model=args.model,
        batch_size=args.batch_size,
        delay=args.delay,
        skip_annotated=not args.no_skip,
    )

    print(f"\nАннотация завершена:")
    print(f"  Всего вопросов: {result['total']}")
    print(f"  Проаннотировано: {result['annotated']}")
    print(f"  Пропущено (уже аннотировано): {result['skipped']}")
    print(f"  Ошибок: {result['errors']}")
    print(f"  Файл: {result['output_path']}")


if __name__ == "__main__":
    main()
