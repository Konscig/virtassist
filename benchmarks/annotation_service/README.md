# Annotation Service

Контейнер для автоматической аннотации датасета с помощью Ollama (локальная LLM).

## Обзор

- **Модель**: qwen3.5:35b-a3b (~20 GB)
- **Платформа**: linux/amd64 (AMD64)
- **Батч**: 10 вопросов
- **Задержка**: 0 сек
- **Сохранение**: каждые 10 вопросов
- **Ожидаемое время**: 10-12 часов для 1305 вопросов

---

## Развертывание на сервере

### Шаг 1: Локальная подготовка

```bash
# Скопировать confluence_urls.json в data/
cp benchmarks/data/confluence_urls.json Submodules/voproshalych/benchmarks/annotation_service/data/

# Образ уже собран в: Submodules/voproshalych/benchmarks/annotation_service/voproshalych-annotation-amd64-v4.tar
```

### Шаг 2: Подключиться к серверу

```bash
ssh -t ave@iv-ml.orienteer.ru fish

# Перейти в директорию сервиса
cd /srv/tgu/annotation_service
```

### Шаг 3: Очистить старые файлы

```bash
# Остановить контейнер
docker compose down

# Удалить контейнер принудительно
docker rm voproshalych-annotation -f

# Удалить старый образ (если был)
docker rmi voproshalych-annotation:latest -f

# Удалить старые tar-файлы
rm -f voproshalych-annotation*.tar
```

### Шаг 4: Загрузить образ на сервер

```bash
# Из локальной машины:
scp Submodules/voproshalych/benchmarks/annotation_service/voproshalych-annotation-amd64-v4.tar ave@iv-ml.orienteer.ru:/srv/tgu/annotation_service/
```

### Шаг 5: На сервере — загрузить образ

```bash
# Загрузить образ
docker load -i voproshalych-annotation-amd64-v4.tar

# Проверить архитектуру (должна быть amd64)
docker image inspect voproshalych-annotation | grep Architecture
```

### Шаг 6: Запустить контейнер

```bash
# Создать директорию data (если нет)
mkdir -p data

# Запустить
docker compose up -d

# Смотреть логи
docker logs -f voproshalych-annotation
```

---

## Мониторинг

### Мониторинг в реальном времени (рекомендуется)

```bash
docker exec -it voproshalych-annotation python3 /app/monitor_progress.py
```

**Вывод:**
```
============================================================
📊 ANNOTATION PROGRESS
============================================================
  Progress: [████████████████████░░░░░░░░░░░░░░░] 42.5%
  Done: 555/1305 questions
  Remaining: 750 questions
============================================================
🚀 SPEED
============================================================
  Current: 0.095 questions/sec (5.7 questions/min)
============================================================
⏱️  ESTIMATED TIME
============================================================
  ETA: 2h 11min
```

**Особенности:**
- 🔄 Автообновление каждые 2 секунды
- 📊 Прогресс бар с процентами
- 🚀 Скорость в реальном времени
- ⏱️  Ожидаемое время до конца
- ✅ Обновление на одной строке (без прокрутки)

**Чтобы остановить:** нажмите `Ctrl+C`

### Проверить статус (однократно)

```bash
docker exec voproshalych-annotation python3 /app/annotate_with_ollama.py \
    --input /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated.json \
    --status
```

Вывод:
```
Статус аннотации:
  Всего вопросов: 1305
  Проаннотировано: XXX
  Осталось: XXX
  Прогресс: XX.X%
  Файл: /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated.json
```

### Просмотреть логи

```bash
docker logs -f voproshalych-annotation
```

Показывает:
- Загрузку модели (первый запуск)
- Запросы к Ollama
- Ошибки парсинга JSON
- Прогресс аннотации

---

## Управление

### Мягкая остановка

```bash
# Запросить остановку после следующего батча
docker exec voproshalych-annotation python3 /app/annotate_with_ollama.py \
    --input /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated.json \
    --stop
```

Контейнер сохранит прогресс и выйдет через 10 вопросов.

### Принудительная остановка

```bash
docker compose down
```

### Возобновление

Просто перезапустить — контейнер найдёт последнюю аннотацию:

```bash
docker compose up -d
```

---

## Работа с volume

Модель qwen3.5:9b сохраняется в Docker volume `ollama_models`.

**Преимущества:**
- Не нужно скачивать модель при каждом запуске
- Пересоздание контейнера не удаляет модель
- Можно копировать volume для бэкапа

### Бэкап модели

```bash
# Показать volumes
docker volume ls

# Копировать volume (для бэкапа)
docker run --rm -v ollama_models:/data -v $(pwd):/backup \
  alpine tar czf /backup/ollama_models.tar.gz -C /data .

# Восстановить
docker run --rm -v ollama_models:/data -v $(pwd):/backup \
  alpine tar xzf /backup/ollama_models.tar.gz -C /data
```

---

## Решение проблем

### Ошибка: "conflict: unable to delete image"

```bash
# Остановить и удалить контейнер
docker compose down

# Принудительно удалить
docker rm voproshalych-annotation -f

# Удалить образ
docker rmi voproshalych-annotation:latest -f
```

### Ошибка: "File /app/data/confluence_urls.json not found"

**Причина:** Файл не был скопирован в data/ на сервере

**Решение:**
```bash
# На локальной машине:
scp benchmarks/data/confluence_urls.json ave@iv-ml.orienteer.ru:/srv/tgu/annotation_service/data/

# На сервере — перезапустить контейнер
docker compose restart
```

### Ошибка: "ModuleNotFoundError: No module named 'ollama'"

**Причина:** Пакет ollama не был установлен в образе

**Решение:** Пересобрать образ с обновлённым Dockerfile (уже исправлено)

---

## Структура файлов

```
annotation_service/
  ├── Dockerfile                    # Описание образа
  ├── docker-compose.yml            # Конфигурация запуска
  ├── entrypoint.sh                # Скрипт запуска
  ├── README.md                    # Этот файл
  ├── monitor_progress.py           # Мониторинг прогресса в реальном времени
  └── data/                        # Директория с датасетом
      ├── dataset_from_20250601_to_20260228_20260303_082311_annotated.json
      └── confluence_urls.json    # Карта URL → название
```

---

## Сборка образа (для локального изменения)

```bash
cd ~/src/github.com/webmasha/voproshalych-personal

# Для AMD64 (сервер)
docker buildx build --platform linux/amd64 --load \
  -f Submodules/voproshalych/benchmarks/annotation_service/Dockerfile \
  -t voproshalych-annotation \
  .

# Сохранить
docker save voproshalych-annotation -o Submodules/voproshalych/benchmarks/annotation_service/voproshalych-annotation.tar
```

---

## Переменные окружения

В `docker-compose.yml` можно изменить:

```yaml
environment:
  - OLLAMA_FLASH_ATTENTION=false   # Отключить flash attention
  - OLLAMA_NUM_THREAD=4          # Количество потоков
  - OLLAMA_NUM_GPU_LAYERS=0     # Количество GPU слоёв (для CPU = 0)
```

---

## Производительность

На сервере (186.3 GB RAM, 186.3 GiB CPU):

- **Скорость аннотации**: ~30-40 сек/вопрос (оценочно)
- **10 вопросов**: ~5-7 минут
- **1305 вопросов**: ~11-14 часов
- **Пиковое использование RAM**: ~8-10 GB
- **CPU**: 4 потока (задаётся в docker-compose.yml)

---

## Особенности

### Резюме после прерывания

Если контейнер был остановлен в середине работы:

1. Датасет в `data/` содержит последние сохранённые аннотации
2. Модель в volume `ollama_models` сохранена
3. При следующем запуске аннотация продолжится с места остановки
4. Не нужно пересобирать образ

### Повреждённые ответы

Скрипт умеет:
- Делать до 3 попыток при ошибках парсинга JSON
- Извлекать JSON из malformed ответов
- Логировать детали ошибок

### Поля аннотации

Каждая запись датасета содержит:
- `annotate_answer_type`: 1 (пустой), 2 (некорректный), 3 (идеальный)
- `annotate_has_source`: 0 (нет), 1 (есть)
- `annotate_url_relevance`: 0 (нет), 1 (да)
- `annotate_answer_url_relevance`: 0 (нет), 1 (да)
- `annotate_is_small_talk`: 0 (по делу), 1 (small talk), 2 (про Вопрошалыча)
