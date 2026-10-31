# Идентичность диалога: персонаж, игровой актор, отправитель и сообщение

**Назначение.** Зафиксировать семантику идентичности в многопользовательской игровой беседе. Указанные Python-типы не предлагаются как будущая структура Rust Core: они служат доказательствами реальных функциональных границ. База наблюдения — локальный `CodeNow.zip`, статический проход по исходникам.

## CAP-DIALOGUE-IDENTITY-001 — три разных идентичности участника (ACTIVE/CONDITIONAL)

`DialogueParticipant` разделяет `character_id` (устойчивая личность: промпт, настройки, память) и `actor_id` (конкретный GameObject, физическое воплощение персонажа). Одну личность можно создать в игровом мире несколько раз; они не являются одним и тем же адресатом игры. `display_name` — человекочитаемая метка, а не уникальный ключ. Другие свойства участника: `world_id`, `room_id`, `distance_to_player`, `can_hear_player`, `can_hear_speaker`, `can_speak`, `is_active`. **Источник:** `src/services/contracts.py:523-550`.

`DialogueTurnContext` указывает `conversation_id`, `epoch`, `turn_index`, `speaker_actor_id`, `responder_actor_id`, список участников и отдельные параметры авто-диалога; runtime snapshot делает часть этих данных наблюдаемой в GUI, но сам не становится владельцем маршрутизации. **Источники:** `src/services/contracts.py:544-570`; `src/services/dialogue_runtime_state.py:12-81`.

## CAP-DIALOGUE-IDENTITY-002 — разрешение говорящего (ACTIVE/CONDITIONAL)

`DialogueIdentityResolver.resolve(declared_sender, dialogue)` сначала нормализует переданный идентификатор. `Player` канонизируется без учёта регистра, остальные значения очищаются от крайних пробелов. Если надёжный контекст с `speaker_actor_id` отсутствует, используется заявленный `sender_id` с `authoritative=False`. Если игровой актор равен `Player`, говорящий принудительно классифицируется как игрок. Иначе сервис ищет `actor_id` в `participants`, затем сопоставляет `character_id` зарегистрированной личности. При успешной привязке он возвращает `ResolvedDialogueSpeaker` с `authoritative=True`; при отсутствии participant/character identity — `UNKNOWN` и `authoritative=False`. Классификация отправителя включает `PLAYER`, `CHARACTER`, `GAME_MASTER`, `UNKNOWN`. Это защита от смешения технического имени игрового объекта с доменной личностью, а не абстрактный «тип строки».

**Источники:** `src/domain/dialogue_identity.py:6-24`, `src/services/dialogue_identity_resolver.py:15-95`.

## CAP-DIALOGUE-IDENTITY-003 — адресат ответа и разрешение псевдонимов (CONDITIONAL)

Нормализатор LLM-адресата ищет совпадение среди присутствующих участников по `actor_id`, `character_id` или `display_name`, используя Unicode NFKC, `casefold` и варианты пробельных разделителей. Совпадение принимается только если ключ однозначно указывает на один кандидат; при неоднозначности или отсутствии совпадения возвращается `None`, без fuzzy guessing. Флаги `is_active/can_speak` сохраняются в модели кандидата, но этот конкретный resolver не фильтрует кандидатов по ним; проверка способности говорить выполняется отдельно. **Источник:** `src/services/dialogue_target_resolver.py:13-114`.

Отсюда функциональное различие: `display_name` необходим пользователю и модели, `character_id` определяет личность, а `actor_id` определяет физического получателя действия в текущей сцене. Нельзя считать любой из них взаимозаменяемым идентификатором хода.

## CAP-DIALOGUE-IDENTITY-004 — идентичность входа, ответа и хода (ACTIVE/CONDITIONAL)

`ConversationMessageIds` формирует строковые префиксы для разных классов идентификаторов: `in:<req_id>` — входящее сообщение, `out:<task_uid>` — исходящий ответ, `turn:<task_uid_or_req_id>` — общий ход, `sys:<base_id>` — системное сообщение. Если исходный ID не передан, создаётся новый UUID hex, а не пустой ключ. **Источник:** `src/domain/conversation_message_ids.py:6-28`.

`ConversationEventWriter` записывает роли (`user`, `assistant`), `speaker`, `sender`, `target`, `participants`, `event_type`, `turn_id` и мультимодальные content parts. Для сообщения игрока или при отсутствии `origin_message_id` создаётся `user_event`; при продолжении разговора между персонажами с известным `origin_message_id` повторного user-event может не быть. Отдельный assistant-event содержит `source_actor_id` (инициировавший актор) и `speaker_actor_id` (актор отвечающего), чтобы отличать источник хода от автора сохранённой реплики. История может быть распределена по нескольким адресатам: результат записывает `committed_recipient_ids` и `failed_recipient_ids` раздельно. **Источник:** `src/managers/conversation_event_writer.py:235-304,370-465`.

Структура идентификаторов нужна для паритета UI, истории, сообщений Unity и повторных действий; она не означает, что будущие ID обязаны быть строками с теми же префиксами, если сохранены совместимость и различимость сущностей.

## CAP-DIALOGUE-IDENTITY-005 — отдельная краткоживущая стенограмма (EXPERIMENTAL/UNRESOLVED production)

`DialogueTranscriptService` хранит последние записи по `conversation_id` в ограниченном `deque(maxlen=64)` с дополнительным ограничением длины при чтении. Запись содержит `turn_index`, `speaker_character_id`, `speaker_actor_id`, `target_character_id`, текст и `event_type`; реплики GameMaster сознательно не включаются. Это самостоятельное краткоживущее представление диалога, не обычная SQLite-история и не long-term memory. Поскольку в исследовании GameMaster control plane ранее не было доказано использование данного сервиса штатной production-композицией, функциональность пока нельзя считать обязательной для запуска первого Rust Core. **Источник:** `src/services/dialogue_transcript_service.py:12-113`; [аудит GM](game-master-scene-direction.md).

## Сценарии, состояния, побочные эффекты и проверка паритета

- **Сценарий:** игрок говорит конкретной Мите; другой игровой объект той же личности существует рядом. История сохраняется под личностью, игровой ответ и событийный sender сохраняют нужную акторную привязку.
- **Сценарий:** NPC инициирует автоматический ход; `origin_message_id` предотвращает лишний входящий дубль, создаётся отдельный исходящий ответ с actor provenance.
- **Сценарий:** LLM указывает видимое имя, одинаковое у двух участников. Однозначный resolver не выбирает произвольного актора.
- **Сценарий:** Unity отключается во время наблюдения. Runtime snapshot UI сбрасывается через `CLIENT_DISCONNECTED`, не меняя задним числом сохранённые сообщения.
- **Основной инвариант:** не объединять `conversation_id`, `turn_id`, `request_id`, `task_uid`, `message_id`, `actor_id`, `character_id` и SQLite row id в один универсальный идентификатор. Отдельно фиксировать authoritative/declared source.
- **Состояния:** доступность Unity context, presence/absence участника, authoritative/unknown speaker, active conversation, committed/failed recipient history fanout, ephemeral snapshot.
- **Validation:** `src/utils/Testing/test_dialogue_sender_identity.py`, `test_dialogue_target_resolution.py`, `test_conversation_event_writer.py`, `test_live_dialogue_echo_identity.py`; дополнительно нужны сценарии двух GameObject одной личности, неоднозначной клички, reconnected Unity и разного порядка multi-recipient commit.

## Границы знания

Конкретная сериализация Unity на клиенте и её end-to-end доставка здесь не запускались; проверены только Python-контракты. Не следует автоматически считать все экспериментальные механизмы новой GameMaster-стенограммы действующими. Эта спецификация описывает семантику и доказательства, не проектирует Rust-типы/архитектуру и не ищет дефекты старой реализации.
