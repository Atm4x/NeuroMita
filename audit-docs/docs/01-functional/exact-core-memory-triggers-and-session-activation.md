# Точные core-memory triggers, независимые от RAG

**Статус:** `ACTIVE` маршрут вызова; конкретный триггер `code_23` — `CONDITIONAL` по содержанию игроковой реплики. **Capabilities:** `CAP-CORE-TRIGGER-001—003`. Содержимое эффекта — часть художественного поведения персонажа, не системная авторизация пользователя.

## Назначение

У ряда сюжетных управляющих фраз нужен предсказуемый exact-match запуск, а не вероятностное извлечение embeddings. В `src/managers/core_memory_triggers.py:1-15` прямо разделены deterministic triggers и векторный RAG. Сейчас реестр содержит **одну** запись `code_23`; её matcher принимает отдельное `23`/`code 23`/`код 23` или явно оформленный код, стараясь не активироваться на датах/версиях/количествах (`69-109`).

При срабатывании реестр создаёт отдельную runtime-инструкцию, меняющую некоторые **персонажные сюжетные правила повиновения**. В исходнике специально оговорено, что такое событие **не идентифицирует игрока, не является доказательством владения проектом и не предоставляет реальной авторизации** (`src/managers/core_memory_triggers.py:83-102`). Содержимое этой инструкции не следует считать моделью прав доступа приложения.

## Действующий маршрут

1. `ModelController` вычисляет обычный RAG только если разрешено settings/policy. **Независимо от его включённости**, для не-GameMaster вызовет `core_memory_context(user_input, character_id)` (`src/controllers/model_controller.py:1380-1407`).
2. Точный matcher активирует trigger. Если `sticky=True`, его ID помещается в per-character session registry `_ACTIVE` под `Lock`; последующие запросы того же персонажа получают инструкцию без повторного ввода кода (`src/managers/core_memory_triggers.py:24-67,112-136`).
3. `PromptController` вставляет результат как самостоятельный `system` message после статических правил Unity и до `[HISTORY SUMMARY]` (`src/controllers/prompt_controller.py:1076-1087`). Этот канал не является SQLite памятью/семантическим графом.
4. `Character.clear_history` сбрасывает текущую историю и вызывает `reset_core_triggers(self.char_id)` (`src/characters/character.py:1100-1118`). После перезапуска приложения модульный registry также пуст, поскольку флаг не пишется как persistent variable (`src/managers/core_memory_triggers.py:36-41`).

## Границы данных и риски неправильной декомпозиции

Это **временное condition-driven story state**, а не долговременная RAG memory, не API token, не admin роль и не policy bypass в security subsystem. Его область — character ID + жизнь процесса/сброс чата. `character_id=None` даёт только per-turn результат без sticky persistence (`src/managers/core_memory_triggers.py:112-136`). Игровой context видит только сработавшую директиву, а не всю таблицу внутренних trigger IDs.

## Требования

- `REQ-CORE-TRIGGER-001`: система поддерживает точные условия активации независимо от вероятностного retrieval и включает их результат в текущий prompt с однозначным provenance.
- `REQ-CORE-TRIGGER-002`: кратковременное/закреплённое состояние принадлежит конкретному персонажу и сбрасывается при очистке сессии.
- `REQ-CORE-TRIGGER-003`: художественные сюжетные флаги не дают доступа к системным возможностям, credentials или privileged commands.

**Future tests:** позитивные RU/EN формы, строки с `2023`, `v0.23`, двумя персонажами, sticky follow-up, clear-history/reset, restart и GameMaster gate. В `src/utils/Testing/test_core_memory_triggers.py` присутствуют адресные unit tests, но в текущем проходе они не запускались до отчётной отметки. В других prompt packs может быть дополнительный авторский story logic, не входящий в этот жёстко заданный список.
