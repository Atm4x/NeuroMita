# Окно диалога, сводки и action memory

**Capability:** `CAP-HIST-005`. **Статус:** ACTIVE для ограничения контекста, CONDITIONAL для compression/maintenance. **Источники:** `src/controllers/history_controller.py:112 prepare_for_prompt`, `:159 _prepare_for_prompt_locked`, `:309 _archive_out_of_window`, `:454 _on_message_completed`, `:516 _process_history_compression`, `:771 _build_compression_plan`, `:860 _start_background_compression`, `:994 _compress_history`, `:1109 _run_compression_request`, `:1306 _commit_summary_state`, `:1363 _summary_cut_index`, `:1432 _maybe_rollup_segments`, `:1485 _apply_layered_compression_result`, `:1540 _build_local_compression_fallback`, `:1786 _sanitize_history_for_llm`.

## Назначение и сценарий

Ограничивать живой контекст модели и сохранять содержание более старой беседы в сводках, не задерживая отправку нового turn синхронным summary request. После завершённого ответа фоновая задача проверяет порог, суммирует старый участок, затем атомарно обновляет summary state.

## Входы и выходы

Активные history rows, memory_limit, policy, summary state, settings компрессии, image policy и character epoch. Выход prepare — PreparedHistory(messages, summary, action_context, last_message_at). Выход compression — обновлённый текст/слои/anchor/count/retained actions, событие обновления UI, опциональные long-term memory candidates.

## Состояние и владельцы

Persisted variables: HISTORY_COMPRESSION_SUMMARY, SUMMARY_COUNT, SUMMARY_ANCHOR, SUMMARY_SEGMENTS с полным префиксом HISTORY_COMPRESSION_; ACTION_MEMORY_RETAINED_REQUESTS. Character.history_epoch — in-memory generation очистки. HistoryController владеет timers, cooldowns, inflight sets и periodic/maintenance counters per character. Это разные состояния: summary_count не используется как позиционная граница.

## Подготовка prompt

Под state lock читаются активная история и summary. Пустые user messages исключаются. Effective limit — 8 для GameMaster, иначе memory_limit, минимум 1. Считаются только видимые user/assistant dialogue messages; system/event messages могут увеличивать фактический размер окна сверх этого числа. Это лимит сообщений, не токенов.

Summary anchor определяет префикс покрытых строк: пока row id положительный и ≤anchor. От оставшейся истории берётся хвост до dialogue limit. Если SAVE_MISSED_HISTORY, summarized rows архивируются (is_active=0); overflow архивируется также при отключённом compression. При включённом compression несуммированный overflow остаётся источником для будущей сводки, хотя в текущий prompt не попадает. Таким образом, window bounded даже при отстающем summarizer, но отсутствие summary может означать временную потерю старого контекста для LLM.

Image quality reduction применяется к выбранной истории, затем фиксируется last timestamp и sanitization оставляет provider messages. Side effect архивации возможен прямо при prepare, несмотря на отсутствие LLM calls. Это уточняет «только чтение» в docstring.

## Sanitization и action memory

Сохраняются user/assistant/system/event roles. TV observation помечается как уже увиденная, дублирование в system input убирается. Speaker/target prefixes поясняют разговор разных персонажей. Time-gap marker ставится перед user/event, чтобы не обучать модель генерировать его в assistant output. Native tool history восстанавливается из structured metadata вместо обычного текста assistant.

При ENABLE_ACTION_MEMORY actions несуммированных assistant turns добавляются к соответствующей реплике как derived context. Для уже суммированных turns используется отдельный короткий bridge retained requests. Нормальный keep_last default 4, диапазон 1—20; emergency caps default 80 records/8000 chars. Эти actions — запрошенные действия, не подтверждение исполнения Unity. Полный action renderer ещё проверить.

## Планирование и триггеры compression

MESSAGE_COMPLETED планирует daemon Timer, default delay 8 s; новое событие заменяет прежний timer. Cooldown провайдера может увеличить задержку. Уже выполняющаяся compression не дублируется: background inflight и singleflight guard per character. Реальная работа поступает в BACKGROUND_LLM pool.

План on-limit: trigger_at=max(round(context_limit×percent), keep_last+1), keep_last ограничен контекстным окном. При достижении порога compress prefix, оставляя keep_last dialogue messages. Periodic mode считает post-response проверки и берёт prefix заданного dialogue count. On-limit имеет приоритет. Defaults в helper не заменяют общую схему settings defaults.

## Targets и layered summary

- layered (default): каждый новый chunk суммируется отдельно без предыдущей summary; добавляется слой text/msg_count/level/created.
- history: новый summary blob включает предыдущую summary, ограниченную по длине.
- memory: summary добавляется как memory type summary; этот путь остаётся достижимым по setting, несмотря на историческую метку в комментарии.

Layered rollup включается при превышении числа слоёв (default 6) или chars (default 8000), объединяет старейшие batch (default 3), оставляет хотя бы один свежий. Это одна попытка rollup, не цикл до строгого лимита. При отказе слои остаются как были. max_segments≤0 или batch≤1 отключает rollup, включая char trigger.

Слои/отрендеренный summary/count/anchor/retained actions записываются одним flush_variables под character lock после проверки epoch. Старый blob может быть прочитан как один migrated слой. Доказательство SQL batch atomicity зависит от Character.flush_variables, будет сверено отдельно.

## Provider request и fallback

Template из HISTORY_COMPRESSION_PROMPT_TEMPLATE с fallback на встроенный текст; multimodal messages переводятся в plain text без base64. HC_PROVIDER выбирает текущий, numeric id или preset по отображаемому имени. Utility request kind compress, одна runner attempt на вызов, наружный compression loop управляет retries/backoff/cooldown. Retry-after может задавать задержку; ожидание реализовано time.sleep, без переданного operation cancellation token.

Если попытки исчерпаны, по default включён local fallback: первые до 24 содержательных сообщений chunk, до 220 chars каждого, общий cap 4000 chars; прежняя summary получает отдельный ограниченный фрагмент. При наличии такого fallback весь выбранный chunk считается summarized и anchor может перейти к его концу. Следовательно, это потенциально lossy сокращение: сохранение полного смысла не гарантируется.

## Отмена, очистка и ошибки

close отменяет pending timers и subscriptions; уже отправленный utility request явно не отменяет. on_history_reset снимает таймеры/counters/cooldowns. После LLM/rollup и в commit проверяется epoch под тем же lock, что используется для check-and-write memory candidates. Late result старой эпохи не должен обновить новую историю. Подтверждённый epoch guard относится к clear_history; изменение истории через отдельные delete/import/regenerate методы может не повышать epoch — проверить при character audit.

Failed queue admission снимает inflight flag и логируется. Невалидная настройка/исключение background task не ломает основной turn. Epoch mismatch отклоняет commit. SQL failure у variable flush может иметь отдельные последствия in-memory state; требуется проверить конкретный character implementation.

## Дополнительные memory jobs

MEMORY_SUMMARY_CANDIDATES_ENABLED (default False) запрашивает 1—5 фактов, default 3, из chunk ≤6000 chars; JSON array допускает priority low/normal/high/critical. Каждый кандидат добавляется с epoch check; сбой не отменяет summary.

Memory maintenance по default каждые 20 completed responses, без отдельного LLM вызова в orchestration; проверяет MEMORY_MAINTENANCE_ENABLED. При занятости не копит очередь. Реальный алгоритм mem.run_maintenance ещё не исследован.

## UI и требования

Compression status и event HISTORY_COMPRESSED обновляют счётчики/контекст. Конкретные экраны будут описаны отдельно. Новая реализация должна различать context window, archival, summary coverage и долговременную память; хранить версию источника фонового результата и атомарный summary checkpoint. Нужны явные сведения о качестве/происхождении fallback summary и правила invalidation при edits/import, а не только при reset.

Возможная реорганизация: snapshot→background derived computation→conditional commit. Это работает и с owned tasks, и с serialized mailbox; выбор по нагрузке и другим state mutations. Rust не гарантирует семантическую полноту summary или отсутствие stale commit без version check. Bibliography/crates отложены до dependency phase.
