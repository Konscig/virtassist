# Руководство по ручной аннотации датасета для RAG-бенчмарков

## Обзор

Ручная аннотация — это процесс **просмотра и уточнения уже сгенерированных датасетов**, а не создание датасета с нуля.

### Основные сценарии

1. **Synthetic dataset** — сгенерирован из чанков через LLM
2. **Manual dataset** — вручную аннотированный synthetic датасет
3. **Real dataset** — реальные вопросы пользователей из БД

---

## 1. Аннотация Synthetic Датасета

### Генерация датасета

```bash
# Synthetic — вопросы генерируются из чанков
uv run python benchmarks/generate_dataset.py \
    --mode synthetic \
    --max-questions 500
```

### Структура датасета

Каждая запись содержит расширенные метаданные:

```json
{
  "id": "syn_a1b2c3d4e5f6",
  "source": "synthetic",
  "question_source": "synthetic|manual",
  "question": "Вопрос пользователя",
  "ground_truth_answer": "Эталонный ответ",
  "chunk_id": 12345,
  "chunk_text": "Текст чанка...",
  "confluence_url": "https://...",
  "relevant_chunk_ids": [123, 456],
  "user_score": 5,
  "question_answer_id": 789,
  "notes": "Комментарий аннотатора"
}
```

### Экспорт для аннотации

```bash
# Экспорт датасета в файл для ручного редактирования
uv run python benchmarks/generate_dataset.py \
    --mode export-annotation \
    --output benchmarks/data/dataset_20260220_123456.json
```

### Поля для аннотации (Synthetic)

| Поле | Тип | Описание |
|------|-----|----------|
| `is_question_ok` | 0/1 | Корректность вопроса |
| `is_answer_ok` | 0/1 | Корректность ответа (ground_truth_answer) |
| `is_chunk_ok` | 0/1 | Корректность источника (chunk) |
| `notes` | строка | Комментарии аннотатора |

### Использование в бенчмарках

```bash
# Запуск на аннотированном датасете
uv run python benchmarks/run_comprehensive_benchmark.py \
    --mode manual \
    --manual-dataset benchmarks/data/dataset_annotated.json \
    --tier all \
    --judge-eval-mode reasoned
```

### Рекомендация по LLM Judge для Synthetic

Для вручную проверенного synthetic-датасета рекомендуемый режим:

- `--mode manual`
- `--judge-eval-mode reasoned`
- `--consistency-runs 2` (или выше для контроля воспроизводимости)

Пример:

```bash
uv run python benchmarks/run_comprehensive_benchmark.py \
    --tier all \
    --mode manual \
    --manual-dataset benchmarks/data/dataset_annotated.json \
    --judge-eval-mode reasoned \
    --consistency-runs 2
```

---

## 2. Аннотация Real User Датасета

Real user датасет используется для анализа реального поведения пользователей и качества ответов бота.

### Экспорт вопросов для аннотации

Запускать из корневой директории проекта (voproshalych):

```bash
# Выгрузка всех QuestionAnswer из БД в JSON
uv run python benchmarks/export_for_annotation.py

# Выгрузка с фильтром по датам (2025-06-01 по 2026-02-28)
uv run python benchmarks/export_for_annotation.py \
    --start-date 2025-06-01 \
    --end-date 2026-02-28

# С лимитом
uv run python benchmarks/export_for_annotation.py \
    --start-date 2025-06-01 \
    --end-date 2026-02-28 \
    --limit 1000
```

По умолчанию создаётся файл `benchmarks/data/dataset_annotation_YYYYMMDD_HHMMSS.json`.
С датами: `benchmarks/data/dataset_from_20250601_to_20260228_YYYYMMDD_HHMMSS.json`.

После запуска аннотации создаётся файл с суффиксом `_annotated`:
`benchmarks/data/dataset_from_20250601_to_20260228_20260303_082311_annotated.json`

Прогресс сохраняется каждые 10 вопросов.

### Как заполнять поля для аннотации

В JSON-файле нужно заполнить следующие поля. Для каждого поля возможные значения:

#### Аннотация через Ollama (РЕКОМЕНДУЕТСЯ)

Запускать из корневой директории проекта (voproshalych), используя `.venv_ollama`:

```bash
# Убедись что Ollama запущена
ollama serve

# В другом терминале - запусти аннотацию
.venv_ollama/bin/python benchmarks/annotate_with_ollama.py \
    --input benchmarks/data/dataset_from_20250601_to_20260228_20260303_082311.json

# С указанием модели (по умолчанию qwen3.5:27b)
.venv_ollama/bin/python benchmarks/annotate_with_ollama.py \
    --input benchmarks/data/dataset_from_20250601_to_20260228_20260303_082311_annotated.json \
    --model qwen3.5:9b

# Не пропускать уже аннотированные (перезаписать)
.venv_ollama/bin/python benchmarks/annotate_with_ollama.py \
    --input benchmarks/data/your_file.json \
    --no-skip

# Меньше логов (batch-size и delay)
.venv_ollama/bin/python benchmarks/annotate_with_ollama.py \
    --input benchmarks/data/your_file.json \
    --batch-size 50 \
    --delay 0.3

# Проверить статус текущей аннотации
.venv_ollama/bin/python benchmarks/annotate_with_ollama.py \
    --input benchmarks/data/dataset_from_20250601_to_20260228_*.json \
    --status

# Запросить мягкую остановку (остановится после следующего батча)
.venv_ollama/bin/python benchmarks/annotate_with_ollama.py \
    --input benchmarks/data/dataset_from_20250601_to_20260228_20260303_082311.json \
    --stop
```

### Мягкая остановка и возобновление

Скрипт поддерживает безопасную остановку без потери прогресса.

**Как остановить:**
1. Запусти в другом терминале:
   ```bash
   .venv_ollama/bin/python benchmarks/annotate_with_ollama.py \
       --input benchmarks/data/dataset_from_20250601_to_20260228_*.json \
       --stop
   ```
2. Скрипт создаст файл `.stop_annotation` в `benchmarks/data/`
3. После обработки следующего батча (10 вопросов) скрипт:
   - Сохранит текущий прогресс в файл `_annotated.json`
   - Завершит работу

**Как проверить статус:**
```bash
.venv_ollama/bin/python benchmarks/annotate_with_ollama.py \
    --input benchmarks/data/dataset_from_20250601_to_20260228_*.json \
    --status
```
Вывод:
- Всего вопросов
- Уже проаннотировано
- Осталось
- Процент выполнения

**Как возобновить:**
Просто запусти команду аннотации снова — скрипт автоматически найдёт файл `_annotated.json` и продолжит с места остановки:
```bash
.venv_ollama/bin/python benchmarks/annotate_with_ollama.py \
    --input benchmarks/data/dataset_from_20250601_to_20260228_*.json
```

Модель автоматически:
1. Для вопросов БЕЗ ответа и confluence_url — заполнит только `annotate_is_small_talk`
2. Для вопросов С ответом или confluence_url — заполнит ВСЕ поля

#### Поля для аннотации

#### annotate_answer_type — Тип ответа

| Значение | Что писать |
|---------|-----------|
| `1` | **Пустой** — поле answer вообще пустое |
| `2` | **Нет ответа / некорректный** — бот ответил, но ответ неполный/некорректный или сомнительный |
| `3` | **Идеальный** — только в крайних случаях, когда семантика вопроса и ответа идеально совпадают |

#### annotate_has_source — Наличие источника

| Значение | Что писать |
|---------|-----------|
| `0` | **Нет** — ссылка на источник отсутствует |
| `1` | **Есть** — ссылка на источник присутствует |

#### annotate_url_relevance — Релевантность URL

| Значение | Что писать |
|---------|-----------|
| `0` | **Нет** — URL не релевантен вопросу |
| `1` | **Да** — URL релевантен вопросу |

*Заполняется ТОЛЬКО если есть источник (has_source=1)*

#### annotate_answer_url_relevance — Релевантность ответа URL

| Значение | Что писать |
|---------|-----------|
| `0` | **Нет** — ответ не соответствует URL |
| `1` | **Да** — ответ соответствует URL |

*Заполняется ТОЛЬКО если есть источник (has_source=1)*

#### annotate_is_small_talk — Тип вопроса

| Значение | Что писать |
|---------|-----------|
| `0` | **По делу** — конкретный вопрос по существу |
| `1` | **Small talk** — привет, пока, как дела и т.п. |
| `2` | **Про Вопрошалыча** — вопросы о системе (кто ты, что умеешь, кто создал) |

### Подсчёт аналитики

После разметки CSV запустите анализ:

```bash
uv run python benchmarks/analyze_annotated.py
```

### Результаты аналитики

Скрипт выводит:

- **Типы ответов**: распределение по категориям (пустой, не найден, ошибка, нормальный)
- **Реальный показатель ответов**: процент вопросов с реальным ответом (типы 3+4)
- **Релевантность**: процент релевантных ответов/URL/связок
- **По платформам**: статистика по VK и Telegram

---

## Цикл работы

### Synthetic Dataset
```
1. Генерация датасета (synthetic)
   │
   ▼
2. Экспорт для аннотации
   │
   ▼
3. Ручная правка (аннотатор)
   │
   ├── Проверка вопросов
   ├── Проверка ответов
   └── Добавление комментариев
   │
   ▼
4. Запуск бенчмарков
   │
   ├── Tier 1 (Retrieval)
   ├── Tier 2 (Generation)
   ├── Tier Judge
   └── Tier UX
```

### Real User Dataset
```
1. Экспорт из БД (export_for_annotation.py)
   │
   ▼
2. Ручная разметка в CSV
   │
   ├── answer_type (1-4)
   ├── answer_relevance (0-2)
   ├── url_relevance (0-2)
   └── answer_url_relevance (0-2)
   │
   ▼
3. Подсчёт аналитики (analyze_annotated.py)
   │
   ├── Реальный % ответов
   ├── Релевантность
   └── Статистика по платформам
```

---

## Принципы аннотации

1. **Фактичность**: ответ должен опираться только на подтверждённые источники
2. **Полнота**: указывайте все релевантные `chunk_id` и `relevant_urls`
3. **Консистентность**: одинаковые типы вопросов размечайте одинаково
4. **Трассируемость**: фиксируйте неоднозначные решения в `notes`

---

## Хранение аннотаций

Аннотации синтетического датасета хранятся в таблице БД `benchmark_annotations`:

```sql
SELECT * FROM benchmark_annotations 
WHERE dataset_file = 'dataset_20260220_123456.json';
```

Поля таблицы:
- `dataset_file` — имя файла датасета
- `item_id` — id записи из датасета
- `is_question_ok`, `is_answer_ok`, `is_chunk_ok` — бинарные метки
- `notes` — текстовые заметки
- `annotator` — имя аннотатора
- `created_at`, `updated_at` — временные метки
