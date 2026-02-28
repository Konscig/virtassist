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

```bash
# Выгрузка всех QuestionAnswer из БД в CSV
cd benchmarks
python export_for_annotation.py
```

По умолчанию создаётся файл `benchmarks/reports/annotation_dataset.csv`.

### Структура CSV

| Колонка | Описание |
|---------|----------|
| `id` | ID записи в БД |
| `question` | Вопрос пользователя |
| `answer` | Ответ бота |
| `confluence_url` | Ссылка на источник |
| `score` | Оценка пользователя (если есть) |
| `user_id` | ID пользователя |
| `platform` | Платформа (vk/telegram) |
| `created_at` | Дата создания |

### Поля для аннотации (Real User)

| Поле | Значения | Описание |
|------|----------|----------|
| `annotate_answer_type` | 1, 2, 3, 4 | Тип ответа |
| `annotate_answer_relevance` | 0, 1, 2 | Ответ релевантен вопросу |
| `annotate_url_relevance` | 0, 1, 2 | URL релевантен вопросу |
| `annotate_answer_url_relevance` | 0, 1, 2 | Ответ релевантен URL |
| `annotate_notes` | текст | Заметки |

#### Расшифровка значений

**answer_type:**
- `1` — Пустой (answer пустой)
- `2` — Ответ не найден (бот не дал ответ)
- `3` — Ошибка (есть URL, но ответ некорректный)
- `4` — Нормальный ответ

**relevance (answer_relevance, url_relevance, answer_url_relevance):**
- `0` — Нет (не релевантно)
- `1` — Да (релевантно)
- `2` — Частично

### Подсчёт аналитики

После разметки CSV запустите анализ:

```bash
python analyze_annotated.py \
    --input benchmarks/reports/annotation_dataset.csv \
    --output benchmarks/reports/annotation_analysis.json
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
