# Руководство по TTA (Time To Answer) бенчмаркам

Данное руководство описывает использование модуля для измерения Time To Answer в системе "Вопрошалыч".

---

## Обзор

TTA (Time To Answer) — время от момента отправки вопроса пользователем до получения ответа. Модуль бенчмарков позволяет измерять:

- **E2E (End-to-End)**: Полное время ответа
- **Компонентное измерение**: Время выполнения каждого этапа
- **Перцентили**: P50, P90, P95, P99
- **Кэш метрики**: Cache Hit Rate

---

## Архитектура измерения

### Этапы обработки запроса

```
User Query → Chatbot → [Context Extraction] → QA Service
                                    ↓
                          [Cache Search] → [Chunk Search]
                                    ↓
                          [LLM Generation] → [Judge Assessment]
                                    ↓
                          [DB Save] → Chatbot → User
```

### Измеряемые компоненты

| Этап | Метрика | Описание |
|------|---------|----------|
| 1 | `TTA_DB_Context` | Формирование контекста диалога из БД |
| 2 | `TTA_Cache_Search` | Поиск в кэше (похожие вопросы) |
| 3 | `TTA_Judge_Cache` | Оценка судьей (кэш) |
| 4 | `TTA_Chunk_Search` | Поиск чанка через pgvector |
| 5 | `TTA_LLM_Generation` | Генерация ответа через Mistral |
| 6 | `TTA_Judge_Generation` | Оценка судьей (генерация) |
| 7 | `TTA_DB_Save` | Сохранение в БД |
| 8 | `TTA_E2E` | Полное время ответа |

---

## Быстрый старт

### 1. Предварительные требования

Убедитесь, что:

- База данных PostgreSQL запущена и загружен дамп
- В БД есть чанки (chunks) и вопросы (question_answer)
- Переменные окружения настроены (`.env.docker`)

```bash
cd Submodules/voproshalych
docker compose --env-file .env.docker up -d --build
```

### 2. Генерация эмбеддингов (если нет)

```bash
cd benchmarks
python generate_embeddings.py --chunks
```

### 3. Запуск бенчмарка

```bash
cd benchmarks
python run_tta_benchmark.py --mode e2e --limit 50
```

---

## Подробное использование

### Режимы бенчмарка

#### E2E (End-to-End)

Измеряет полное время ответа:

```bash
python run_tta_benchmark.py --mode e2e --limit 100
```

**Метрики:**
- `TTA_E2E_mean`, `TTA_E2E_P50`, `TTA_E2E_P90`, `TTA_E2E_P95`, `TTA_E2E_P99`
- `TTA_DB_Context`, `TTA_Cache_Search`, `TTA_Chunk_Search`
- `TTA_LLM_Generation`, `TTA_Judge_Cache`, `TTA_Judge_Generation`
- `TTA_DB_Save`
- `Cache_Hit_Rate`

#### Component

Измеряет время выполнения каждого компонента отдельно:

```bash
python run_tta_benchmark.py --mode component --limit 100
```

**Метрики:**
- Все компонентные метрики (как в E2E)
- `TTA_QA_mean`, `TTA_QA_P50`, `TTA_QA_P95` — агрегированное время QA-сервиса

#### All

Запускает оба режима:

```bash
python run_tta_benchmark.py --mode all --limit 100
```

---

## Генерация датасета

### Типы датасетов

#### Simple (по умолчанию)

Простые вопросы из реальной БД:

```bash
python run_tta_benchmark.py --dataset-type simple --limit 50
```

#### With Chunks

Вопросы с информацией о чанках:

```bash
python run_tta_benchmark.py --dataset-type with-chunks --limit 50
```

#### Stratified

Стратифицированный датасет с заданной пропорцией кэша:

```bash
python run_tta_benchmark.py --dataset-type stratified --limit 100 --cache-ratio 0.3
```

### Использование существующего датасета

```bash
python run_tta_benchmark.py --dataset benchmarks/data/tta_dataset_20260201_120000.json
```

### Сохранение датасета

```bash
python run_tta_benchmark.py --dataset-type simple --limit 100 --save-dataset
```

Датасет будет сохранен в `benchmarks/data/tta_dataset_YYYYMMDD_HHMMSS.json`.

---

## Интерпретация результатов

### Основные метрики

| Метрика | Значение | Что означает |
|---------|---------|--------------|
| `TTA_E2E_P50` | 2000ms | 50% вопросов отвечаются за 2 секунды |
| `TTA_E2E_P95` | 5000ms | 95% вопросов отвечаются за 5 секунд |
| `Cache_Hit_Rate` | 30% | 30% вопросов найдены в кэше |

### Компонентный анализ

| Метрика | Значение | Что означает |
|---------|---------|--------------|
| `TTA_LLM_Generation_mean` | 1500ms | Среднее время генерации LLM |
| `TTA_Cache_Search_mean` | 100ms | Среднее время поиска в кэше |
| `TTA_Chunk_Search_mean` | 50ms | Среднее время поиска чанка |

### Узкие места

Поиск узких мест в производительности:

1. **Высокое `TTA_LLM_Generation`** — проблемы с LLM API
2. **Высокое `TTA_Cache_Search`** — линейный поиск не оптимизирован
3. **Низкий `Cache_Hit_Rate`** — мало вопросов с оценкой 5
4. **Высокое `TTA_DB_Context`** — проблемы с запросами к БД

---

## Примеры запуска

### Пример 1: Быстрый тест (10 вопросов)

```bash
python run_tta_benchmark.py --mode e2e --limit 10 --verbose
```

### Пример 2: Полный анализ (100 вопросов)

```bash
python run_tta_benchmark.py --mode all --limit 100 --dataset-type stratified --save-dataset
```

### Пример 3: Компонентный анализ

```bash
python run_tta_benchmark.py --mode component --limit 50 --dataset-type with-chunks
```

### Пример 4: Использование собственного датасета

```bash
python run_tta_benchmark.py --mode e2e --dataset my_dataset.json
```

---

## Сохранение результатов

Результаты сохраняются в `benchmarks/reports/tta_benchmark_<mode>_<timestamp>.json`.

Формат результата:

```json
{
  "timestamp": "20260201_120000",
  "mode": "e2e",
  "metrics": {
    "TTA_E2E_mean": 2456.78,
    "TTA_E2E_P50": 2100.0,
    "TTA_E2E_P95": 4500.0,
    "Cache_Hit_Rate": 0.32,
    "TTA_LLM_Generation_mean": 1234.56,
    ...
  }
}
```

---

## Оптимизация производительности

### Улучшение кэш hit rate

Добавьте больше вопросов с оценкой 5:

```python
# В chatbot/main.py при оценке ответа пользователем
if score == 5:
    # Вопрос будет использоваться в кэше
    pass
```

### Оптимизация поиска в кэше

Замените линейный поиск на векторный индекс:

```python
# TODO: Использовать pgvector для cache search вместо линейного
```

### Уменьшение времени LLM генерации

1. Используйте более быструю модель
2. Уменьшите `max_tokens` в промпте
3. Уберите искусственные задержки `sleep(1.1)` для тестов

---

## Troubleshooting

### Ошибка: Нет чанков в БД

```bash
# Загрузите дамп и сгенерируйте эмбеддинги
python load_database_dump.py
python generate_embeddings.py --chunks
```

### Ошибка: Нет вопросов в БД

Загрузите дамп серверной БД:

```bash
# Скопируйте дамп и загрузите в БД
# Затем запустите бенчмарк
```

### Ошибка: Модель эмбеддингов не найдена

Проверьте переменную окружения `EMBEDDING_MODEL_PATH` в `.env.docker`.

### Медленное выполнение

- Уменьшите `--limit`
- Используйте более быстрое окружение
- Отключите логирование (уберите `--verbose`)

---

## Дополнительная информация

### Структура модуля

```
benchmarks/
├── models/
│   └── tta_benchmark.py       # Основной класс TTABenchmark
├── utils/
│   └── tta_metrics.py         # Утилиты для измерения времени
├── data/
│   └── tta_dataset_generator.py  # Генератор датасетов
├── run_tta_benchmark.py      # CLI скрипт
└── docs/
    └── TTA_GUIDE.md          # Это руководство
```

### Ключевые классы

- `TTABenchmark`: Основной класс бенчмарка
- `TTAMetricsCollector`: Коллектор метрик времени
- `TTATimingContext`: Контекстный менеджер для измерения времени

---

## Контакты и поддержка

Для вопросов и предложений обращайтесь к разработчикам проекта "Вопрошалыч".
