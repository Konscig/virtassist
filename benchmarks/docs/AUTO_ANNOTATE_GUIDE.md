# Автоматическая аннотация датасета с помощью LLM

## Обзор

Скрипт `auto_annotate.py` использует LLM (например, GPT-4o-mini) для автоматической аннотации вопросов и ответов из базы данных. Это позволяет быстро разметить большие объёмы данных без ручной работы.

---

## Быстрый старт

### 1. Экспорт датасета из БД

```bash
uv run python export_for_annotation.py
```

Создаст файл `benchmarks/data/dataset_annotation_YYYYMMDD_HHMMSS.json`

### 2. Запуск автоматической аннотации

```bash
uv run python auto_annotate.py \
    --input benchmarks/data/dataset_annotation_20260228_123456.json
```

По умолчанию:
- Модель: `gpt-4o-mini`
- Выходной файл: `{input_name}_annotated.json`
- Задержка между запросами: 0.5 сек

### 3. Подсчёт аналитики

```bash
uv run python analyze_annotated.py \
    --input benchmarks/data/dataset_annotation_20260228_123456_annotated.json
```

---

## Параметры

| Параметр | Описание | По умолчанию |
|-----------|----------|---------------|
| `--input` | Путь к входному JSON | (обязательно) |
| `--output` | Путь к выходному JSON | `{input}_annotated.json` |
| `--model` | Модель для аннотации | `gpt-4o-mini` |
| `--batch-size` | Логировать каждые N вопросов | 10 |
| `--delay` | Задержка между запросами (сек) | 0.5 |

---

## Как работает

Скрипт для каждого вопроса:
1. Отправляет вопрос, ответ и URL LLM
2. LLM анализирует и возвращает JSON с аннотацией
3. Скрипт записывает результат в выходной файл

### Поля аннотации

LLM проставляет следующие поля:

| Поле | Значения | Описание |
|------|---------|----------|
| `answer_type` | 1, 2, 3 | Тип ответа |
| `has_source` | 0, 1 | Наличие источника |
| `url_relevance` | 0 | Релевантность URL |
| `answer_url_relevance` | 0 | Релевантность ответа URL |
| `is_small_talk` | 0, 1, 2 | Тип вопроса |

### Логика LLM

- **answer_type=1**: поле answer пустое
- **answer_type=2**: ответ бесполезен, не отвечает на вопрос, или "извините не нашёл"
- **answer_type=3**: полезный развёрнутый ответ
- **has_source=1**: есть ссылка в confluence_url ИЛИ ссылка в тексте ответа
- **is_small_talk=0**: вопрос по делу
- **is_small_talk=1**: small talk (привет, пока, как дела)
- **is_small_talk=2**: про Вопрошалыча (кто ты, что умеешь)

---

## Примеры использования

### Использовать другую модель

```bash
uv run python auto_annotate.py \
    --input benchmarks/data/dataset_annotation.json \
    --model gpt-4o
```

### Указать выходной файл

```bash
uv run python auto_annotate.py \
    --input benchmarks/data/dataset_annotation.json \
    --output benchmarks/data/my_annotated.json
```

### Уменьшить задержку (для быстрых API)

```bash
uv run python auto_annotate.py \
    --input benchmarks/data/dataset_annotation.json \
    --delay 0.1
```

---

## Требования

- `OPENAI_API_KEY` в переменных окружения
- Доступ к интернету для запросов к OpenAI

Пример:
```bash
export OPENAI_API_KEY=sk-...
```
