# Возможности, имеющие исходники, но не подтверждённые в основной композиции

**Назначение:** отделить активные функции NeuroMita от экспериментов и библиотечных инструментов. Наличие `.py` файла или импорта dependency недостаточно, чтобы объявить обязательное требование к первой полной Rust-версии. Это *дополнительная проверка reachability*, не попытка удалить или исправить старый код.

**Источник:** `CodeNow.zip`, поиск usages по `src/**/*.py` с исключением `src/utils/Testing` для первичного runtime. **Уверенность:** `CONFIRMED` для обнаруженных direct import/call paths; `UNRESOLVED` для возможного динамического вызова из внешних пакетов/скриптов и пользовательского standalone запуска.

| Кандидат | Где действительно реализован | Проверенный путь использования | Классификация / решение аудита |
|---|---|---|---|
| Semantic command canonicalizer `CommandParser` | `src/utils/command_parser.py:11-20,23-273`: загружает embeddings команд, нормализует XML-like `<c>/<a>/<e>…` теги, similarity threshold и category switching | В `src/` обнаружены определение и `if __name__ == '__main__'` self-demo `:275-305`; явных production callers извне этого модуля поиск не обнаружил | **UNRESOLVED/standalone**. Семантическую автозамену тегов нельзя принимать за обязательный runtime путь structured commands без вызова из LLM/Unity. Не редактировать. |
| `RemotePathResolver` | `src/DSL/path_resolver.py:154-236` | `src/characters/character.py` и `src/managers/dsl_manager.py` формируют `LocalPathResolver` в текущем prompt pipeline. По исходникам другие direct callsites `RemotePathResolver` не обнаружены | **UNRESOLVED**: remote prompt file resolver как возможный backend, не подтверждённая активная функция; локальный DSL — активен и [описан](../01-functional/dsl-executable-prompt-contract.md). |
| Новый scheduler/directive registry GameMaster | `src/services/game_master_scheduler.py:8-28`, `src/services/game_master_services.py:11…`; `src/domain/game_master.py` | `ensure_game_master_services()` присутствует в своём модуле; вызовы этой функции из основного `src/` кроме определения поиск не обнаружил; legacy GameMaster task/response gateway может существовать отдельно | **EXPERIMENTAL/UNRESOLVED** для долгосрочных директив и tick scheduler. Не смешивать с подтверждённым старым GM turn route; [подробнее](../01-functional/game-master-scene-direction.md). |
| Web/VTT FastAPI и mock provider | `src/web/server.py`, `src/web/vtt/*`, `src/web/mock_api/*` | Самостоятельный web ASGI entrypoint; в desktop startup (`src/__main__.py`, `src/controllers/main_controller.py`) запуск сервера не найден | **Standalone/EXPERIMENTAL**; не обязательный скрытый HTTP server desktop. [Контракт](../01-functional/standalone-web-surface.md). |
| In-process AI adapter for RAG tests | `src/handlers/ai_engine/inprocess_engine.py:10-126` | `register_inprocess_engine()` обнаружен в `src/utils/Testing/rag_tester/rag_tester_core.py:579-580`, а не обычном runtime core | **TEST/EXPERIMENTAL**: отдельный regression/tuning worker, не основание переносить inference в Rust Core. |
| Event constants without literal producer/consumer | `src/core/events.py` | 288 event IDs объявлены, 202 имеют статические direct emit/subscribe callsites, остальные могут вызываться через динамические механизмы или быть устаревшими | **Не классифицировать автоматически LEGACY** только по отсутствию AST-callsite. [Подробный индекс](event-producer-consumer-callsite-index.md). |

## Важные ограничения выводов

Поиск `rg` по именам не исчерпывает `getattr`, string-built imports, Python plugins, вызовы subprocess и внешние callers. В особых случаях пользовательский standalone mode может существовать без использования в основном запуске. Поэтому классификация `UNRESOLVED` — не утверждение об окончательной ненужности, а требование дополнительной проверки до переноса в обязательный функциональный паритет.

## Условия изменения статуса

1. Найден trace от **активной** точки входа/зарегистрированной GUI action/Unity event/feature flag до конкретной реализации.
2. Подтверждены входы, выходы и фактическое состояние результата (а не только создание объекта).
3. Для условных ветвей доказан доступный пользователю способ включения/конфигурация и наличие зависимостей.
4. Записан validation case, который отличит наличие класса от реально работающей функции.

**Следующий проход:** искать dynamic registration/CLI invocations только для этих явно перечисленных непроверенных кандидатов, если всё ещё требуется объективное решение о full parity. Не устранять Legacy, не встраивать экспериментальные зависимости в Rust Core только по их наличию.
