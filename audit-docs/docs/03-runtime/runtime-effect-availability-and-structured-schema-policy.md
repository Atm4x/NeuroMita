# Доступность игровых эффектов и состав structured schema в каждом LLM-запросе

**Цель:** объяснить, почему ответ модели не имеет постоянного набора допустимых операций: фактическая функциональная поверхность рассчитывается для каждого запроса из подключения Unity, настроек, персонажа, глубины tools и наличия изображений. **Не** копировать текущие Python namespace/схемы как целевую Rust-архитектуру. **Статус:** ACTIVE path, отдельные effects CONDITIONAL.

## CAP-RUNTIME-SCHEMA-001 — три категории сегментов

`src/services/runtime_capabilities.py:15-47` классифицирует поля `StructuredSegment`:

- **Unity-only:** `emotions`, `animations`, `idle_animations`, `movement_modes`, `visual_effects`, `clothes`, `interactions`, `face_params`, `allow_sleep`, `intents`. Для их исполнения нужен game connection. При удалённом режиме и включённом `REMOTE_ONLY_STRUCTURED_FIELDS_EXCLUSION_ENABLED` исключаются из schema.
- **Program-owned:** `commands`, `music`, `start_game`, `end_game`. Core может обработать эти группы и без Unity; отсутствие game connection не должно автоматически отключать каждую.
- **Shared:** `text`, `target`, `hint` — содержание/маршрутизация, не требуют игрового runtime.

`resolve_runtime_capabilities` получает `GameLinkService.is_connected()`, возвращает tri-state `connected=True/False/None`, `remote_only` и excluded field list. Unknown game-link **не** приравнивается к disconnected. Настройка выключает исключение schema даже при `connected=False`; это пользовательская опция, а не физическое подключение. `src/services/runtime_capabilities.py:50-120`.

## CAP-RUNTIME-SCHEMA-002 — дополнительная фильтрация на уровень запроса

`src/services/structured_response_capabilities.py:171-253` формирует request-specific `StructuredResponseCapabilities`:

| Поля/возможность | Guard / отличие |
|---|---|
| `start_game`, `end_game` | Отключены при `ENABLE_GAMES=False`, даже если это program-owned поля |
| `entities`, `relations` | Требуют одновременно `RAG_ENABLED` и `GRAPH_EXTRACTION_ENABLED` |
| `reminder_add`, `reminder_delete`, `timer_add` | Исключены при `REMINDERS_ENABLED=False` |
| `tool_call` | Требуется structured output, включённый tools gate, не-`off` mode, доступные enabled tools и `tool_depth < tool_max_depth` |
| `image_description` | Требует реально переданные изображения и `IMAGE_INLINE_DESCRIPTION=True` |
| `secret_exposed` | Для соответствующего вида персонажа при нераскрытом секрете — поле required, для остальных/уже раскрытого — исключается |
| `reasoning` | Зависит от schema reasoning capability |
| `working_state` | Требует `ENABLE_WORKING_STATE=True` и structured output |
| `custom_fields` | Включено только при наличии собственных параметров персонажа |

Важно: **schema field availability — не результат выполнения действия**. Наличие `tool_call` в модели не означает, что вызов разрешён после исчерпания глубины; наличие `emotions` в raw ответе не доказывает, что Unity сейчас может исполнить эмоцию. `ModelController` строит профиль перед запросом и повторно использует его при continuation (`src/controllers/model_controller.py:1626-1662,2687+`).

## CAP-RUNTIME-SCHEMA-003 — сквозное согласование промпта, JSON Schema и postprocessing

- `PromptController` использует тот же snapshot для `[System State]` и DSL-переменных `GAME_CONNECTED` / `UNITY_EFFECTS_AVAILABLE` (`src/controllers/prompt_controller.py:243-258,376-390`), чтобы модель не получала взаимоисключающие утверждения о доступных эффектах.
- `ModelController._sanitize_structured_segment_fields` обрабатывает output: профиль capabilities может очистить поля, которые не разрешены для текущего запроса (`src/controllers/model_controller.py:373-395`). Это отдельная граница валидации после ответа; исключение из provider schema не заменяет её.
- Способность работать с изображениями вычисляется из реально передаваемых provider messages с рекурсивным обходом `image_url`, `inline_data`, typed image parts (`src/services/structured_response_capabilities.py:153-168`). Это не просто UI toggle «Camera enabled».
- Статический Provider API может различаться в способе объявления schema, но источник функциональных capabilities один (`provider_schema_options`: `structured_response_capabilities.py:256-273`).

## Конкретные требования и проверки паритета

1. Соединённая Unity vs отключённая/неизвестная → корректные schema exclusions и system-state сообщения; `commands/music` остаются доступными при других выполненных условиях.
2. `ENABLE_GAMES=False` удаляет start/end game независимо от Unity; disable reminders и graph extraction отдельно фильтруют поля.
3. Для неполных/поздних tool continuations depth-bound ограничивает новые вызовы; при двух разных запросах schema может различаться.
4. Изображение фактически присутствует/отсутствует — не тот же факт, что настройка vision разрешена.
5. При недоступности game result нельзя считать игровое действие исполненным только потому, что LLM вернула field; нужен отдельный consumer/ack.

**Источник подтверждения:** статический код. Реальные LLM/schema conformance, Unity executor, входящие provider responses и мультимодальные тесты не запускались. Целевой Rust API и выбор schema serialization ещё не проектировались.
