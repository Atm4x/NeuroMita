# Автодиалог, продолжения и idle

Статус: ACTIVE/CONDITIONAL в Unity e7c7ae42. Orchestration игрового клиента не является заранее выбранной границей нового Rust backend.

## Участники и player admission

SpeakerRoster получает active actors, исключает Player/GameMaster/Cart/None, отсутствующих/спящих и farther50 units. Cart branch существует, но IsCartAvailable всегдаfalse. Explicit target приоритетнее roster[0]; участие проверяется перед submission и processing/presentation. Actor может уснуть между request и result, готовый ответ тогда может не примениться.

Player submit отвергается при SpeechStateReporter.IsActive/пустом тексте/непригодном target. Submitted здесь — локальный id enqueue, не Python acceptance. После admission меняются speaker priority, engagement/life signals, показывается player line. Action prefix `*Совершает действие:` использует особый history color без обычной смены priority. Dispatch failure пытается восстановить original draft.

## Автоответы

DialogueSpeakerOrder хранит chain turn count, count per speaker, latest source/full response/address map, addressed queue. Новый player response resetPending очищает цепочку. NPC source turn расходует quota; continuation может её не увеличивать. Новые addressed segments ставятся вперед и заменяют прежнюю цель того же recipient; self/inactive/empty targets отбрасываются.

Max chain ограничивает auto turns, rounds задаёт quota per speaker. Runtime clamp rounds1..24, chain1..200. Сначала выбирается addressed target, затем speaker с невыполненной quota, предпочтительно другой, чем latestSource. Приоритет определяется order points; player-turn leader теряет25 points. Без addressed segment всё равно возможен quota-based auto reply.

Planner включает full reply и адресованный target segment в инструкции. Routing ждёт0.25s и DialogueControl idle, рассылает listener info, затем SendReact L2 DialogueAuto. Enable auto dialogue проверяется result processor перед scheduling; внутри routing после await нет увиденного generation/cancel guard. Смена настроек/сцены в ожидании требует проверки.

## Продолжение и moderation

Intent dialogue.continue резервирует отдельный consecutive budget текущего character: reset при player/non-continue response/смене character, clamp0..12, default3. Reservation происходит до send; инструкция сообщает remaining. Исчерпание пишет runtime explanation. Это не retry и не тот же budget, что rounds/chain.

Registered active/enabled GameMaster считает NPC replies до repeat1..100 и ставит observationPending. После dialogue idle отправляется hidden game_master_observe. ApplySettings сбрасывает cadence/pending. Python loaded_settings принудительно передаёт GM_ON=false, поэтому штатная sync выключает эту автоматическую cadence даже при сохранённом Python GM_ON=true. get_task_status legacy path читает setting иначе. Замысел projection и другие GM пути ещё уточнить; нельзя объявлять весь GM неиспользуемым.

## Idle и engagement

Idle scheduler использует GameplayPauseClock.DeltaTime и check примерно1s. Default threshold180s меняется game settings. Conversation busy останавливает accumulation и сбрасывает interval после завершения. Pause/sleep/settling/unavailable target запрещают реакцию. Inactivity budget default3, clamp0..5, резервируется до send и в просмотренном пути не возвращается при remote block/failure.

Player message/direct interaction/sleep finished сбрасывают budget; walking/looking/proximity — нет. Shared conversation обновляет communication time/idle timer без reset budget. Другие queued reactions также обновляют idle timer без нового budget. Социальная неактивность отличается от raw-input AFK.

## Runtime events

Per-character buffer≤30 entries/2000 sum chars, entry≤512, oldest eviction. Add объединяет duplicate last event/mergeKey и увеличивает Count. Capture копирует ids/rendered messages, commit удаляет captured ids. ReplaceOrAdd меняет id при изменении, защищая late completion. Add duplicate Count id не меняет: occurrence после capture может исчезнуть при commit прежнего snapshot. Это versioning risk, а не требование повторить buffer implementation.

System info обычно остаётся до следующего turn. Explicit system_info_flush запускает generation при pending events/instruction. Старый systemMessages adapter есть, полная reachability producers не закрыта.

## Требования и источники

Разделить player admission, event coalescing, recipient addressing, fairness/quota, continuation, moderation и social inactivity. Reservations требуют policy reject/failure; async auto scheduling — scene/source generation. Будущие границы Rust/Unity не фиксируются текущими static classes.

Прочитаны полностью DialogueContinuationPolicy/SpeakerOrder/Roster/AutoReplyPlanner/MessageRoutingService/GameMasterService/GameMaster/IdleDialogueScheduler/ParticipationPolicy/RuntimeContextBuffer и PlayerEngagementRuntime. DialogueApi/Messages основные методы, ServerSettings.ApplyFromDictionary и MitaCore.ApplyServerSettings. Addressed message construction/identity resolver, полный executor и presentation ещё не завершены.
