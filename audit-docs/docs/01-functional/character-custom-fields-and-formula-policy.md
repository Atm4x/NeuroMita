# Пользовательские параметры персонажей и безопасные формулы

**Срез:** `CodeNow.zip`, 2026-10-30; действующий `Character.process_structured_response`. **Статус:** `CONDITIONAL`: обработка зависит от конфигурации `custom_params` и наличия `structured.custom_fields`. Это функциональное правило персонажа, а не требование сохранить Python AST/eval в Rust.

## CAP-CHAR-CUSTOM-001 — параметры из пользовательского config

**Регистрация/вход:** `src/managers/character_config_manager.py:145-209` читает config, валидирует элементы custom_params через Pydantic model и отбрасывает неверные, не завершая загрузку всего персонажа. `src/characters/character.py:225-250` загружает список и начальные значения. `Character.process_structured_response` нормализует `structured.custom_fields` в dict (`character.py:536-542`) и проходит params в порядке конфига (`:544-624`). Каждая запись определяет имя хранимой переменной, `change_command` (опциональный ключ входа), тип, ограничители и `formula` или операцию `add`/`set`.

**Порядок вычисления:** 1) числовое приведение float/int, иначе исходное значение; 2) ограничение входа `change_min/change_max`; 3) только для `op=add` ограничение delta `[-max_change,+max_change]`; 4) `formula` (если непуста) имеет приоритет над `op` — иначе `add`/`set`; 5) числовой результат ограничивается `min/max`; 6) `set_variable`. Источники `character.py:548-619`. В `formula` контекст включает все текущие `variables` плюс `current`, `value`, alias `change_command` и `variable_name` (`:38-56`). Если два custom_params работают с одной variable, результат предыдущего может повлиять на следующую в том же response. При ошибке отдельного param идёт лог и продолжается следующий (`:620-623`): это **не атомарное применение набора**.

**Отдельно от built-in stats:** `adjust_attitude/boredom/stress` используют `_adjust_bounded_stat` (`character.py:1218-1284`): rounded delta ± configurable hard limit(default6), optional min/max(default0/100), некорректный reversed range отключается с error log. Прежний built-in stat путь нельзя автоматически объединить с custom formulas без проверки отличающейся политики.

## CAP-CHAR-CUSTOM-002 — expression DSL, не Python eval в произвольном окружении

`_evaluate_custom_param_formula` вызывает `core.safe_eval.safe_eval_expression` с whitelist `max,min,abs,int,float,round` (`src/characters/character.py:28-56`). В `src/core/safe_eval.py:101-118,120-266` expressions парсятся через `ast.parse(..., mode='eval')` и обрабатываются только известными AST node visitors. Недопустимы `Attribute`, индексация или внешние вызовы вне whitelist; неизвестные имена отклоняются. Это ограниченный пользовательский вычислительный язык, а не безопасное разрешение любых Python expressions. Подробные операторы/типы должны быть перенесены в отдельный формальный compatibility grammar только после анализа тестов и реальных конфигов.

**Тесты:** `PYTHONPATH=src python -m unittest src/utils/Testing/test_safe_eval.py src/utils/Testing/test_character_stats.py -q` — **17 tests, OK**. Они подтверждают проверенные whitelist/unsafe AST rejection и stat bounds в текущем Python, но не completeness grammar в альтернативной реализации. Отдельная попытка `test_character_history_clear.py` не запустилась из-за отсутствующего `PyQt6`; это средовое ограничение, не негативный результат самого функционала.

## Требования к новому приложению

- `REQ-CHAR-CUSTOM-001`: schema и порядок применения `change_min/max → max_change(add) → formula/op → result min/max` должны быть представлены как наблюдаемые правила, допускающие отдельный validation.
- `REQ-CHAR-CUSTOM-002`: interpreter должен быть детерминированным и ограничивать язык вычислений, не предоставляя arbitrary code execution. Определить допустимые числа, строки, сравнения, функции, ошибки деления и max AST complexity по рабочим конфигам/fixtures.
- `REQ-CHAR-CUSTOM-003`: сохранять per-character state, применение изменений в порядке и явные `applied/skipped/failed`; эффект частичного применения должен быть обозначен, а не молча маскироваться общим success.
- `REQ-CHAR-CUSTOM-004`: built-in stats и custom params различаются policy; новый механизм может их унифицировать только после явного compatibility proof.

**Неясности:** реальные `custom_params` в пользовательских prompt packs отсутствуют в этом source snapshot; cross-field dependencies в production, persistence result after mid-way failure, repeated variable names, parameter type coercion boundaries и Undo после regeneration нужно проверять отдельно.

**Связано:** [characters](characters.md), [structured responses](../03-runtime/structured-response-contract.md), [prompt DSL](prompt-language-and-packs.md).
