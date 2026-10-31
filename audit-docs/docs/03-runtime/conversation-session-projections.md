# Контекст групповой беседы: авторитет Unity, проекция Core и отображение в GUI

**Назначение.** Разделить реальное расписание ходов Unity, информацию, передаваемую LLM, и ephemeral состояние для отображения в десктопном чате. Статус текущей цепочки **ACTIVE/CONDITIONAL**: Unity dialogue snapshot приходит в выполняемую Python-запросом генерацию; desktop projection и подписка UI подтверждены. Это описание функции, не proposal о будущем Rust state management.

## CAP-DIALOGUE-VIEW-001 — входной снимок и идентичность беседы

**Источники:** `src/services/contracts.py:522-569,571-576,603-733`; `src/controllers/chat_controller.py:503-535`; `src/controllers/prompt_controller.py:1118-1143`; `src/game_connections/handlers/actions/create_task.py` (передача `dialogue`/participants в dispatch).

`DialogueTurnContext` содержит `conversation_id`, `epoch`, `turn_index`, `speaker_actor_id`, `responder_actor_id`, счетчик автоматических ответов, максимальное число автоматических ходов, `spoken_actor_ids`, `world_id`, `room_id`, `participants`. У каждого участника есть **разные** `actor_id` (конкретный Unity GameObject) и `character_id` (личность, подсистема промпта/истории), плюс display name, room/world, дистанция и флаги hearing/speaking/active.

Parser допускает словарь и уже построенный типизированный контекст, нормализует boolean и числовые поля и отбрасывает участников без `actor_id`. Отдельные `client_*` поля — диагностическая копия настроек Unity, а не разрешение Core самостоятельно планировать очередь говорящих.

**Операционная модель:** Unity определяет, кто говорит, кто отвечает и какие автоматические ходы допускаются; Core подготавливает LLM turn для заданной личности. Group prompt показывает присутствующих и прямо оговаривает принадлежность speaker order и follow-up scheduling Unity. Отдельный `PlayerMessageSource` (`APPLICATION/GAME/NONE`) описывает происхождение *ввода игрока*; его нельзя смешивать с `DialogueRuntimeSource` (`UNITY/NONE`) — это метка происхождения *снимка беседы для UI*.

## CAP-DIALOGUE-VIEW-002 — одно ephemeral состояние текущей беседы для UI

**Источники:** `src/services/dialogue_runtime_state.py:15-117`; `src/services/contracts.py:603-639`; `src/controllers/chat_controller.py:209-220,518-529`; `src/controllers/gui/chat_panel_view_model.py:39-75`; `src/ui/widgets/chat_panel.py:99-114`; `src/ui/chat/dialogue_presentation.py:6-40`; `src/ui/windows/app_window_base.py:2071-2099`.

В момент начала request с валидным `dialogue.conversation_id` ChatController публикует `DialogueRuntimeSnapshot`, сохраняя `source`, id/epoch/turn, активность auto-dialogue, лимиты, speaker/responder и сокращённую presentation-проекцию участников. Snapshot держится под `RLock`; обновление вызывает `Events.Dialogue.RUNTIME_STATE_CHANGED`.

`DialogueRuntimeStateService` подписан на `Events.Server.CLIENT_DISCONNECTED` и очищает **именно Unity** snapshot при разрыве. `reset(source)` также способен не затронуть snapshot другой provenance. Runtime snapshot не является ни историей сообщений, ни authoritative модулем маршрутизации, ни durable session store. Сам сервис комментирует это как `ephemeral UI observation state`.

**Отображение:**

| UI элемент | Поведение |
|---|---|
| Заголовок чата | Без активной беседы: `Conversation with <selected character>`; при одной Mita — имя; при 2–3 — список; при большей группе — `Conversation with Mitas (N)` |
| Participant list | Использует `character_id`/display_name, удаляет повторяющиеся case-insensitive отображаемые имена, не показывает GameMaster |
| Индикатор источника | Для `UNITY` показывает `Game`, иначе не показывается |
| Chat surface recipients | При explicit request character ids используется этот набор; иначе участники из активного snapshot, и только если выбранный character входит в набор; иначе fallback только на него |
| ChatPanelViewModel | Подписывается на `RUNTIME_STATE_CHANGED`, асинхронную активность генерации и связанные события персонажей/пресетов; сохраняет UI-specific state отдельно |

**Сценарий:** Unity сообщает состав группы → Core получает новый turn context → ChatController публикует presentation snapshot → ViewModel обновляет заголовок и список допустимых UI-проекций → `PromptController` строит контекст конкретного отвечающего персонажа. Исчезновение связи очищает ephemeral projection; persistent chat history не обязана удаляться.

## CAP-DIALOGUE-VIEW-003 — ограниченная локальная стенограмма как отдельная исследуемая возможность

**Статус:** **EXPERIMENTAL / UNRESOLVED production registration**. **Источники:** `src/services/dialogue_transcript_service.py:10-101`; `src/services/game_master_services.py:11-21`; `src/services/game_master_context_builder.py:94-115`.

Имеется `DialogueTranscriptService` с in-memory per-conversation deque (по умолчанию до 64 записей), structured entries `turn_index`, speaker actor/character, target, event_type, text. Чтение по умолчанию ограничено последними 12 записями и 12 000 символами. Player и Mita имеют convenience methods; GM строки игнорируются. В production-вызовах создания/записи стенограммы вне нового GameMaster control-plane не найдены. Поэтому это **не** подтверждение, что в текущем продукте используется отдельная краткая group transcript для GameMaster; обычная история описана в другом документе.

## Контракты для последующего проектирования, без выбора архитектуры

1. `conversation_id` / epoch / turn index — координаты конкретной беседы, а `character_id` / `actor_id` — другая плоскость идентичности.
2. Детали участника в LLM/Unity не равны сокращённому GUI projection: UI не получает полномочий самостоятельно выбирать следующий ход.
3. Автоматические ответы, локальная история персонажа и временная стенограмма группы решают разные пользовательские задачи.
4. Источник player-authored текста и источник видимого session snapshot имеют разные типы и не должны обобщаться одним флагом «из игры».
5. Смена беседы, disconnect, поздно пришедший ответ, переключение персонажа и многократные actor instances одной личности требуют отдельных validation cases.
6. Не включать экспериментальный transcript в требования обязательного паритета без runtime path; дальнейший аудит — проверить регистрацию других источников `RUNTIME_STATE_CHANGED` и UI consumer edge-cases.

**Смежные документы:** [history](../01-functional/history.md), [Unity auto-dialogue](../01-functional/unity-auto-dialogue.md), [scene director](../01-functional/game-master-scene-direction.md), [chat UI](../02-ui/chat-stream-history-and-message-actions.md).
