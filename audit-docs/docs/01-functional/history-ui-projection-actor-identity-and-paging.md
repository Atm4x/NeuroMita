# История в GUI: identity персонажей, проекция ролей и постраничная доставка (Pass 12)

**Статус:** ACTIVE. **Источники:** `src/managers/history_ui_projector.py:8-138`, `src/controllers/model_controller.py:794-923,2825-2857`, `src/core/message_content.py`, `src/core/tv_observation.py`, `src/utils/Testing/test_history_ui_projector_multi_mita.py`, `test_dialogue_sender_identity.py`, `test_history_epoch_guard.py`. Никакие исходные файлы при аудите не менялись.

## CAP-HISTORY-VIEW-001 — видимое сообщение не является сырой записью

`HistoryUiProjector.project_for_ui()` принимает хранимые сообщения и формирует новые словари представления. Допускаются роли `user`, `assistant`, `system`, `event` (`history_ui_projector.py:44-55`). `event` преобразуется в `system`; сообщения `user` без видимого содержания пропускаются. Отображение `user` зависит от фактических `speaker` и `sender`, а не только от строки `role`:

- При явной идентичности `Player` и отсутствии другого актёра отображается пользовательская сторона (`role=user`).
- Если `role=user`, но `speaker/sender` — другая Мита, сообщение показывается со стороны персонажей (`assistant`) и получает структурированный блок `meta` с именем говорящего.
- Старые записи `role=user` без `speaker/sender` продолжают выглядеть как пользовательские (legacy compatibility).
- Системное сообщение, исторически помещённое под `user` и начинающееся с `[Системное]:`, не переопределяется как речь ассистента лишь из-за наличия `speaker`.
- При указанном `target`, не равном Player, мета-метка может содержать `speaker → target`; если структурированные сегменты имеют несколько разных целей, добавление стрелки оставлено downstream renderer.

Отдельная ветвь TV observation нормализует пользовательский `tv_observation`, удаляет повторяющийся форматированный текст из обычных text parts, вставляет специализированную часть содержимого; event наблюдения может быть показан как пользовательская реплика независимо от исходной event role (`history_ui_projector.py:70-111`). Это представление сообщения, а не редактирование его raw identity или перезапись хранилища.

## CAP-HISTORY-VIEW-002 — запрос конкретного собеседника и пагинация

`_on_load_history` получает `request_id` и `character_id` из запроса UI, выбирает captured character, сбрасывает текущий offset и получает последние записи (`get_recent_messages(limit,offset=0)`). Результат отправляется через `history_loaded` c `request_id`, `character_id`, `messages`, `total_messages`, `loaded_offset`. Если персонаж отсутствует, возвращается пустая страница с идентификаторами запроса (`model_controller.py:794-851`).

`_on_load_more_history` использует `character_id` или captured `_history_character_id`, проверяет соответствие текущей проекции и, если существуют более старые записи, вызывает history manager с увеличенным `offset`. Ответ `more_history_loaded` несёт character identity и новый offset (`model_controller.py:853-923`).

**Критически различать:** pagination offset в raw storage и число видимых пузырей GUI. Фильтрация невидимых `user` сообщений может уменьшить количество видимых строк, не изменяя смысл уже загруженных raw message identity. Для fallback `load_history()` существуют отдельные ветви, поэтому только успешные `get_recent_messages` тесты не доказывают весь функционал миграции.

## CAP-HISTORY-VIEW-003 — legacy user correction и identity игрового актора

`ModelController._fix_projected_ui_message` возвращает legacy/Player сообщение на пользовательскую сторону и удаляет вспомогательный `meta` block, если raw role и identity этому соответствуют. В отличие от plain role-only маппинга, сообщение другой Миты с `role=user` остаётся на стороне персонажа (`model_controller.py:2825-2857`).

Отдельная входная классификация Unity-актора (`test_dialogue_sender_identity.py`) рассматривает `Player` как авторитетную identity, умеет сопоставлять actor ID с зарегистрированным персонажем и не должна приписывать неизвестному non-player actor права Player. Это отдельный контракт **кто произнёс сообщение**, не просто как рисуется bubble.

## Validation Pass 12

Адресный offline-run:

`PYTHONPATH=src python -m pytest -q src/utils/Testing/test_history_ui_projector_multi_mita.py src/utils/Testing/test_dialogue_sender_identity.py src/utils/Testing/test_history_epoch_guard.py` → **22 passed**. Это прямое свидетельство проекции, identity входного sender и хранения summary/memory после history reset с epoch protection. Тесты изолируют и извлекают отдельные методы из Python source; настоящее переключение вкладок GUI, сетевое Unity событие и конкурентная загрузка нескольких реальных персонажей не запускались.

- **REQ-HISTORY-VIEW-001:** независимо представлять persisted role, sender/speaker/target/actor и UI role; при показе межперсонажных сообщений не приравнивать `role=user` к Player.
- **REQ-HISTORY-VIEW-002:** страницы запрашиваются и доставляются с идентификатором персонажа; response initial page коррелируется с request ID; raw pagination и displayed row count не должны подменять друг друга.
- **REQ-HISTORY-VIEW-003:** TV observation и segment-level target имеют типизированную семантику presentation; legacy записи остаются отображаемыми без изменения их смысла.

**Открыто:** живой GUI E2E при быстром переключении active character, нескольких simultaneous paging requests, старых форматах событий и реальной Unity-доставке. См. [history/memory lifecycle](history-memory-lifecycle-and-user-operations.md), [actor/message identity](dialogue-actor-and-message-identity-contracts.md), [raw event ledger](../00-research/raw-string-event-reachability-and-ui-bridges.md).
