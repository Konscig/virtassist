# Проверка аннотаций на сервере

## Обзор

Гайд по проверке того, что аннотации реально проставляются в датасет.

---

## Способ 1: Мониторинг в реальном времени (рекомендуется)

```bash
docker exec -it voproshalych-annotation python3 /app/monitor_progress.py
```

Вывод:
```
Progress: 0.8% (10/1305)
Remaining: 1295 questions
Speed: 0.014 questions/sec (0.8 questions/min)
ETA: 26h 59min
```

**Ключевой показатель:** `Progress` увеличивается = аннотации проставляются

---

## Способ 2: Просмотр последних аннотаций через grep

```bash
docker exec voproshalych-annotation sh -c "grep 'annotate_is_small_talk.*\"[12]' /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated_annotated.json | tail -5"
```

Пример вывода:
```json
    "annotate_is_small_talk": "0",
    "annotate_is_small_talk": "0",
    "annotate_is_small_talk": "1",
    "annotate_is_small_talk": "0",
    "annotate_is_small_talk": "0"
```

**Ключевой показатель:** Появляются записи со значениями `"1"` или `"2"`

---

## Способ 3: Подсчет количества аннотированных вопросов

```bash
docker exec voproshalych-annotation sh -c "grep -c '\"annotate_is_small_talk\": \"[012]\"' /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated_annotated.json"
```

Вывод:
```
42
```

**Ключевой показатель:** Число увеличивается = аннотации проставляются

---

## Способ 4: Просмотр структуры данных в файле

```bash
docker exec voproshalych-annotation sh -c "python3 -c \"
import json
from pathlib import Path

path = Path('/app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated_annotated.json')
with open(path) as f:
    items = json.load(f)

# Найти последнюю аннотацию
for i, item in enumerate(items):
    if item.get('annotate_is_small_talk') is not None:
        last = i

print(f'Всего вопросов: {len(items)}')
print(f'Последняя аннотация на индексе: {last}')
print()
print('Пример аннотированного вопроса:')
print(json.dumps(items[max(0, last-5):last+1][0], indent=2, ensure_ascii=False))
\"
"
```

Пример вывода:
```
Всего вопросов: 1305
Последняя аннотация на индексе: 41

Пример аннотированного вопроса:
{
  "question": "какой номер общежития?",
  "answer": "Номер общежития можно узнать у коменданта...",
  "annotate_answer_type": "2",
  "annotate_has_source": "1",
  "annotate_url_relevance": "1",
  "annotate_answer_url_relevance": "0",
  "annotate_is_small_talk": "0"
}
```

**Ключевой показатель:** Видим полный вопрос со всеми полями аннотации

---

## Способ 5: Открытие папки через VS Code SSH

Да, можно открыть папку прямо через VS Code!

### Метод A: Remote SSH (рекомендуется)

1. **Установить VS Code Remote - SSH**:
   - Открой VS Code
   - Ctrl+Shift+X → "Remote - SSH: Connect to Host..."
   - Или Extensions → Search "Remote - SSH"

2. **Добавить SSH конфигурацию**:
   ```bash
   # Файл: ~/.ssh/config на локальной машине
   Host forecast
       HostName iv-ml.orienteer.ru
       User ave
       ForwardAgent yes
   ```

3. **Подключиться к серверу**:
   ```
   - Ctrl+Shift+P → "Remote-SSH: Connect to Host..."
   - Выбери "forecast"
   ```

4. **Открыть папку**:
   ```
   - File → Open Folder...
   - Введи: /srv/tgu/annotation_service/data
   ```

Теперь ты видишь файлы прямо в VS Code и можешь:
- Открывать JSON файлы
- Искать аннотации (Ctrl+F → `annotate_`)
- Сравнивать файлы
- Редактировать (при необходимости)

### Метод B: SSH FS (альтернатива)

1. **Установить SSH FS Extension**:
   - Extensions → Search "SSH FS"
   - Установи от "Naorue"

2. **Подключиться**:
   - Нажми на иконку SSH FS в левой панели
   - "+ New Connection"
   - Host: `iv-ml.orienteer.ru`
   - Username: `ave`
   - Connect

3. **Открыть файлы**:
   - В левом браузере файлов увидишь структуру
   - Открой `/srv/tgu/annotation_service/data/`

### Метод C: SFTP через FileZilla (если VS Code не работает)

1. **Установить FileZilla**
2. **Подключиться**:
   - Host: `iv-ml.orienteer.ru`
   - User: `ave`
   - Port: `22`
   - Protocol: `SFTP`
3. **Открыть папку**:
   - `/srv/tgu/annotation_service/data/`

---

## Способ 6: Просмотр прогресса через статус-команду

```bash
docker exec voproshalych-annotation python3 /app/annotate_with_ollama.py \
    --input /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated.json \
    --status
```

Вывод:
```
Статус аннотации:
  Всего вопросов: 1305
  Проаннотировано: 42
  Осталось: 1263
  Прогресс: 3.2%
  Файл: /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated_annotated.json
```

---

## Способ 7: Просмотр одной конкретной аннотации

```bash
docker exec voproshalych-annotation sh -c "python3 -c \"
import json

with open('/app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated_annotated.json') as f:
    items = json.load(f)

# Показать аннотацию вопроса 0 (после 10 - это будет 10)
idx = 10
print(f'Вопрос {idx}:')
print(f'  Вопрос: {items[idx][\"question\"][:100]}...')
print(f'  Ответ: {items[idx].get(\"answer\", \"\")[:100]}...')
print(f'  answer_type: {items[idx].get(\"annotate_answer_type\", \"N/A\")}')
print(f'  has_source: {items[idx].get(\"annotate_has_source\", \"N/A\")}')
print(f'  url_relevance: {items[idx].get(\"annotate_url_relevance\", \"N/A\")}')
print(f'  answer_url_relevance: {items[idx].get(\"annotate_answer_url_relevance\", \"N/A\")}')
print(f'  is_small_talk: {items[idx].get(\"annotate_is_small_talk\", \"N/A\")}')
\"
"
```

Вывод:
```
Вопрос 10:
  Вопрос: можно ли сдать экзамен досрочно?...
  Ответ: Да, можно сдать экзамен досрочно...
  answer_type: 2
  has_source: 1
  url_relevance: 0
  answer_url_relevance: 0
  is_small_talk: 0
```

---

## Краткая справка: Проверить аннотации одной командой

```bash
# Показать количество аннотаций
docker exec voproshalych-annotation sh -c "grep -c '\"annotate_is_small_talk\": \"[012]\"' /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated_annotated.json"

# Показать последние 3 аннотации
docker exec voproshalych-annotation sh -c "grep 'annotate_is_small_talk.*\"[12]' /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated_annotated.json | tail -3"

# Показать полный статус
docker exec voproshalych-annotation python3 /app/annotate_with_ollama.py --input /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated.json --status
```

---

## Рекомендуемый рабочий процесс

### Во время аннотации:

1. **Запуск аннотации:**
   ```bash
   cd /srv/tgu/annotation_service
   bash restart.sh
   ```

2. **В другом терминале - мониторинг:**
   ```bash
   docker exec -it voproshalych-annotation python3 /app/monitor_progress.py
   ```

3. **Каждые 5-10 минут - проверка через grep:**
   ```bash
   # Сколько аннотаций сейчас
   docker exec voproshalych-annotation sh -c "grep -c '\"annotate_is_small_talk\": \"[012]\"' /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated_annotated.json"
   ```

4. **При необходимости - открытие в VS Code:**
   - Ctrl+Shift+P → "Remote-SSH: Connect to Host..."
   - Выбери "forecast"
   - Открой папку `/srv/tgu/annotation_service/data`
   - Открой файл `dataset_from_20250601_to_20260228_20260303_082311_annotated_annotated.json`
   - Искай по слову `annotate_`

### После завершения аннотации:

1. **Проверить финальный статус:**
   ```bash
   docker exec voproshalych-annotation python3 /app/annotate_with_ollama.py --input /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated.json --status
   ```

2. **Скачать аннотированный датасет:**
   ```bash
   # Копировать с сервера на локальную машину
   scp ave@iv-ml.orienteer.ru:/srv/tgu/annotation_service/data/dataset_from_20250601_to_20260228_20260303_082311_annotated_annotated.json ~/Downloads/
   
   # Или через rsync
   rsync -avz ave@iv-ml.orienteer.ru:/srv/tgu/annotation_service/data/*.json ~/Downloads/
   ```

---

## Что означают поля аннотации

- **`annotate_answer_type`**: Тип ответа (1, 2, или 3)
- **`annotate_has_source`**: Есть ли ссылка на источник (0 или 1)
- **`annotate_url_relevance`**: Релевантен ли URL вопросу (0 или 1)
- **`annotate_answer_url_relevance`**: Использует ли ответ информацию из URL (0 или 1)
- **`annotate_is_small_talk`**: Is small talk (0 = нет, 1 = приветствие, 2 = прощание)

Все поля должны быть проставлены для вопросов с ответами.

---

## Решение проблем

### Аннотации не проставляются

1. **Проверить логи контейнера:**
   ```bash
   docker logs -f voproshalych-annotation
   ```

2. **Проверить загружена ли модель:**
   ```bash
   docker exec voproshalych-annotation ollama list
   ```

3. **Проверить отвечает ли Ollama:**
   ```bash
   docker exec voproshalych-annotation curl http://localhost:11434/api/tags
   ```

4. **Проверить есть ли ошибки в аннотациях:**
   ```bash
   docker logs voproshalych-annotation | grep -i error
   ```

### Файл не найден

```bash
# Проверить какие файлы есть в data/
docker exec voproshalych-annotation ls -la /app/data/

# Возможно имя файла отличается от ожидаемого
```

### VS Code не подключается

1. **Проверить SSH подключение:**
   ```bash
   ssh ave@iv-ml.orienteer.ru
   ```

2. **Проверить путь к файлам:**
   ```bash
   ls -la /srv/tgu/annotation_service/data/
   ```

3. **Использовать SSH FS вместо Remote SSH** (см. Способ 5B)

---

## Быстрые команды для проверки

```bash
# Количество аннотаций
docker exec voproshalych-annotation sh -c "grep -c '\"annotate_is_small_talk\": \"[012]\"' /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated_annotated.json"

# Последние 5 аннотаций
docker exec voproshalych-annotation sh -c "grep 'annotate_is_small_talk.*\"[12]' /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated_annotated.json | tail -5"

# Статус через Python
docker exec voproshalych-annotation python3 /app/annotate_with_ollama.py --input /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated.json --status

# Мониторинг в реальном времени
docker exec -it voproshalych-annotation python3 /app/monitor_progress.py

# Открыть папку в VS Code (Remote SSH)
# Ctrl+Shift+P → "Remote-SSH: Connect to Host..." → Выбери "forecast" → Open Folder → /srv/tgu/annotation_service/data
```
