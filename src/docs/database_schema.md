# Схема базы данных NeuroMita

## Описание
База данных `neuromita.db` использует SQLite для централизованного хранения истории чатов и памяти персонажей. Это заменяет предыдущую JSON-структуру в директориях `Histories/{character}/`.

Две основные таблицы:
- **history**: Хранит сообщения чатов для каждого персонажа.
- **memory**: Хранит факты и воспоминания для каждого персонажа.

Поля `faiss_vector` (BLOB) подготовлены для будущей интеграции с FAISS для векторного поиска.

## Mermaid ER-диаграмма

```mermaid
erDiagram
    HISTORY {
        INTEGER id PK "Auto-increment ID"
        TEXT character_name "Имя персонажа"
        TEXT role "Роль (user, assistant)"
        TEXT content "Содержимое сообщения"
        TEXT timestamp "Временная метка"
        BLOB faiss_vector "Вектор для FAISS (на будущее)"
    }
    MEMORY {
        INTEGER id PK "Auto-increment ID"
        TEXT character_name "Имя персонажа"
        TEXT key "Ключ факта"
        TEXT value "Значение факта"
        TEXT priority "Приоритет (low/medium/high)"
        TEXT memory_type "Тип памяти (fact/summary/event)"
        TEXT timestamp "Временная метка"
        BLOB faiss_vector "Вектор для FAISS (на будущее)"
    }
    HISTORY ||--o{ MEMORY : "related_to"
```

## SQL-схема (для справки)
```sql
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_name TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    faiss_vector BLOB
);

CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_name TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    priority TEXT DEFAULT 'medium',
    memory_type TEXT DEFAULT 'fact',
    timestamp TEXT NOT NULL,
    faiss_vector BLOB
);
```

Эта схема обеспечивает совместимость с существующими моделями: `HistoryManager` и `MemoryManager` будут фасадами над `DatabaseManager`, возвращая данные в формате, аналогичном JSON (списки словарей).