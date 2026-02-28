# TESTING_GUIDE

## Содержание

- [Обзор](#обзор)
- [Внешние метрики](#внешние-метрики-external-metrics)
- [Внутренние метрики](#внутренние-метрики-internal-metrics)
- [Запуск бенчмарков](#запуск-бенчмарков)
- [Дашборд](#дашборд)

---

## Обзор

Данное руководство описывает систему метрик для оценки качества RAG-системы "Вопрошалыч".

Метрики разделены на две категории:
- **Внешние метрики** — для демонстрации проблем в работе чат-бота
- **Внутренние метрики** — технические бенчмарки для глубокой оценки компонентов

---

## Внешние метрики (External Metrics)

Внешние метрики используются на этапе предпроектного обследования для демонстрации проблем в работе чат-бота.

### Анализ пользователей

Скрипт: `benchmarks/analyze_users_domain.py`

| Метрика | Описание |
|---------|----------|
| `total_users` | Всего уникальных пользователей |
| `users_with_questions` | Пользователей с вопросами |
| `users_without_questions` | Пользователи без вопросов |
| `users_without_questions_rate` | Процент пользователей без вопросов |
| `users_with_unanswered` | Пользователи с безответными вопросами |
| `users_with_unanswered_rate` | Процент пользователей с безответными вопросами |
| `total_questions` | Всего вопросов |
| `avg_questions_per_user` | Среднее число вопросов на пользователя |
| `questions_per_user_distribution` | Распределение вопросов по пользователям |
| `users_by_platform` | Распределение по платформам (VK, Telegram, MAX) |
| `questions_timeline` | Вопросы по дням (последние 90 дней) |

**Запуск:**
```bash
cd benchmarks
python analyze_users_domain.py
```

**Вывод:** `benchmarks/reports/users_domain_analysis.json`

### Анализ вопросов

Скрипт: `benchmarks/analyze_real_users_domain.py`

| Метрика | Описание |
|---------|----------|
| `total_questions` | Всего вопросов |
| `with_answers` | Вопросы с ответами |
| `without_answers` | Вопросы без ответов |
| `with_answers_rate` | Процент вопросов с ответами |
| `scored_questions` | Вопросов с оценками |
| `score_distribution` | Распределение оценок |
| `avg_question_length` | Средняя длина вопроса |
| `top_tokens_all` | Топ токенов в вопросах |

**Запуск:**
```bash
cd benchmarks
python analyze_real_users_domain.py
```

**Вывод:** `benchmarks/reports/real_users_domain_analysis.json`

---

## Внутренние метрики (Internal Metrics)

Внутренние метрики — технические бенчмарки для оценки качества отдельных компонентов RAG-системы.

### Tier 0: Embedding Quality

Оценка качества векторного пространства чанков.

| Метрика | Описание | Baseline |
|---------|----------|----------|
| `avg_nn_distance` | Среднее расстояние до ближайшего соседа | 0.30 |
| `density_score` | Плотность векторного пространства | 3.00 |
| `avg_pairwise_distance` | Среднее попарное расстояние | 0.45 |

### Tier 1: Retrieval Quality

Оценка качества поиска релевантных чанков.

| Метрика | Описание | Baseline |
|---------|----------|----------|
| `mrr` | Mean Reciprocal Rank | 0.80 |
| `hit_rate@1` | Hit Rate @ 1 | 0.70 |
| `hit_rate@5` | Hit Rate @ 5 | 0.90 |
| `hit_rate@10` | Hit Rate @ 10 | 0.95 |

### Tier 2: Generation Quality

Оценка качества сгенерированных ответов.

| Метрика | Описание | Baseline |
|---------|----------|----------|
| `avg_faithfulness` | Верность ответов контексту | 4.50 |
| `avg_answer_relevance` | Релевантность ответов | 4.20 |
| `avg_answer_correctness` | Правильность ответов | 4.20 |

### Tier 3: End-to-End Quality

Оценка качества полного пайплайна.

| Метрика | Описание | Baseline |
|---------|----------|----------|
| `avg_e2e_score` | E2E оценка | 4.20 |
| `avg_semantic_similarity` | Семантическое сходство | 0.85 |

### Tier Judge: LLM Judge

Оценка качества с помощью LLM Judge.

| Метрика | Описание | Baseline |
|---------|----------|----------|
| `consistency_score` | Согласованность оценок | 0.90 |
| `error_rate` | Процент ошибок | 0.05 |
| `avg_latency_ms` | Средняя задержка (мс) | 3000 |

### Tier Judge Pipeline: Production Judge

Оценка с использованием production-ready модели.

| Метрика | Описание | Baseline |
|---------|----------|----------|
| `accuracy` | Точность | 0.85 |
| `precision` | Precision | 0.85 |
| `recall` | Recall | 0.85 |
| `f1_score` | F1 Score | 0.85 |

### Tier UX

UX метрики.

| Метрика | Описание | Baseline |
|---------|----------|----------|
| `cache_hit_rate` | Cache hit rate | 0.40 |
| `context_preservation` | Сохранение контекста | 0.70 |
| `multi_turn_consistency` | Консистентность в мульти-тёрн | 0.70 |

### Utilization

Анализ использования чанков.

| Метрика | Описание |
|---------|----------|
| `total_chunks` | Всего чанков |
| `used_chunks` | Использовано чанков |
| `unused_chunks` | Неиспользовано чанков |
| `utilization_rate` | Процент использования |

### Topic Coverage

Анализ покрытия тем.

| Метрика | Описание |
|---------|----------|
| `n_topics` | Количество тем |
| `total_questions` | Всего вопросов |
| `avg_chunks_per_topic` | Среднее число чанков на тему |

---

## Запуск бенчмарков

### Комплексный запуск

```bash
cd benchmarks
python run_comprehensive_benchmark.py
```

### Отдельные компоненты

```bash
# Генерация эмбеддингов
python generate_embeddings.py

# Анализ использования чанков
python analyze_chunk_utilization.py

# Анализ покрытия тем
python analyze_topic_coverage.py

# Анализ пользователей
python analyze_users_domain.py

# Анализ вопросов
python analyze_real_users_domain.py
```

---

## Дашборд

### Запуск

```bash
cd benchmarks
python run_dashboard.py
```

Дашборд будет доступен по адресу `http://localhost:7860`

### Вкладки

1. **Run Details** — детали запусков бенчмарков
2. **Runs Registry** — реестр всех запусков
3. **Metric History** — история изменения метрик
4. **Tier Comparison** — сравнение tier'ов
5. **Run Dataset** — просмотр датасета запуска
6. **Vector Space** — визуализация векторного пространства
7. **Chunk Utilization** — использование чанков
8. **Topic Coverage** — покрытие тем
9. **Domain Insights** — анализ вопросов (внешние метрики)
10. **User Analytics** — анализ пользователей (внешние метрики)
11. **LLM Comparison** — сравнение LLM моделей
12. **Judge Comparison** — сравнение judge моделей
13. **Prod Judge Comparison** — сравнение production judge
14. **Справка** — помощь

---

## Интерпретация результатов

### Внешние метрики (проблемы)

- Если `users_without_questions_rate` > 50%: много пользователей не используют чат-бот
- Если `users_with_unanswered_rate` > 30%: значительная часть пользователей не получает ответов
- Если `without_answers_rate` > 50%: более половины вопросов остаются без ответов

### Внутренние метрики (технические)

- Tier 0: Проблемы с векторным пространством → пересмотр модели эмбеддингов
- Tier 1: Проблемы с поиском → улучшение чанкинга или индексации
- Tier 2: Проблемы с генерацией → настройка prompt'ов или модели
- Tier 3: Проблемы E2E → комплексная оптимизация
