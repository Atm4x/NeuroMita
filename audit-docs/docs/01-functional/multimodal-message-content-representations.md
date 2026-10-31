# Мультимодальное содержимое сообщения: разные представления одного события

**Статус:** ACTIVE. **CAP-CONTENT-001—004** (дополнительная декомпозиция), источник `src/core/message_content.py`, реальные потребители `src/managers/history_manager.py`, `src/controllers/history_controller.py`, `src/managers/history_ui_projector.py`, `src/managers/action_memory.py`, `src/handlers/llm_providers/gemini_provider.py`. Не является предложением оставить Python-класс `MessageContentCodec` в целевой архитектуре.

## Назначение

Пользовательское/модельное сообщение может быть либо строкой, либо упорядоченным списком типизированных частей (`text`, `image_url`, другие виды). Из **одного исходного сообщения** NeuroMita получает несколько разных проекций: multimodal payload для LLM, текст с плейсхолдерами для summary, текст только из человеческих сегментов для embeddings, запись БД с отдельной метаинформацией и отображение для UI. Эти проекции **намеренно не эквивалентны**.

## Основные преобразования по реальному коду

| Проекция | Вход | Наблюдаемое правило | Для чего используется |
|---|---|---|---|
| `parts` / `has_visible_content` | строка / list of dicts | Строка проверяется на непустой текст; в list видимой считается непустая `text` или любая часть с заданным типом | Admission пустых сообщений и projection UI (`history_ui_projector.py`) |
| `to_prompt_text` | mixed content | `text` → текст, `image_url` → `[image]`, неизвестный `type` → `[type]` | Формирование текста для сжатия истории (`history_controller.py`) без передачи inline base64 в summary prompt |
| `to_embedding_text` | mixed content | Строка сохраняется; для списка объединяются **только** текстовые части через newline; картинки и unknown type исключены | Индексация текста истории (`history_manager.py`) |
| `split_for_db` | mixed content | Текстовые части объединяются через newline в поле content, прочие части остаются отдельными словарями meta | Сохранение сообщений (`history_manager.py`), optional mapping data:image → storage URI |
| `merge_from_db` | text + stored parts | Восстанавливает текстовую часть, картинки и unknown type; отдельный callback получает original/clean image для описания/UI | Восстановление истории и media representation (`history_manager.py`) |
| `prepend_text` / `append_text` | mixed content | Префикс добавляется к первой `text` или новой первой части; суффикс становится последней текстовой частью | Временные контекстные пометки и блок памяти действий (`history_controller.py`, `action_memory.py`) |

Незнакомые типы **не удаляются автоматически при DB round-trip**, если представляют словарь со значением `type`. В текстовом summary это лишь явная метка. Предусмотрен однократный warning для каждого неизвестного типа — диагностика, не отдельная пользовательская функция.

## Контракт изображений

`image_url.url` может исходно содержать `data:image...`, затем `split_for_db` вызывает опциональную функцию переноса изображения в storage и сохраняет преобразованную ссылку. При восстановлении `merge_from_db` локальные пути (`is_local_file` или не-HTTP/non-data URL) могут быть преобразованы обратно в адрес для потребителя. Дополнительные `detail` и `display_role` сохраняются в UI-clean object; `on_image` передаёт сведения для проекции описаний. Это разные аспекты медиа: **изображение как LLM-вложение**, **хранимый blob/path**, **UI-представление** и **текстовая видимость**.

`split_for_db` для списка текстовых частей не сохраняет исходную структуру text parts полностью: она объединяется в одну строку с newline, тогда как прочие части остаются отдельными. Поэтому требование новой реализации — сохранить функционально значимый порядок и не потерять дополнительные части, **не** обязательно повторить старую SQL-схему byte-for-byte. Дословный byte-level round-trip всех text-part границ старый код не гарантирует.

## End-to-end сценарии

1. Пользователь отправляет текст + картинку. В LLM-проходе возможна мультимодальная отправка, в БД сохраняется текст отдельно от media metadata, в сжатии изображения становятся `[image]`, в поисковый embedding попадает только текст.
2. Модель/сервис возвращает дополнительную типизированную часть. Даже если summary и embedding её не используют, сохранение/восстановление не должно незаметно терять компонент.
3. В историю добавляется временный текстовый префикс/суффикс. Исходные нетекстовые элементы остаются на месте; при appending новый текстовый элемент добавляется в конец.
4. В UI историческое сообщение может считаться видимым даже без буквального текста, если оно содержит изображение/другую типизированную часть.

## Доказательства и будущие проверки

- `src/core/message_content.py:40-258`: единая реализация всех проекций.
- `src/managers/history_manager.py:530-631`: embedding-text и DB round-trip.
- `src/controllers/history_controller.py:1537-1538,1759,1863`: сжатие и UI/gap decoration.
- `src/managers/action_memory.py:139-140`: суффиксы action memory.
- `src/utils/Testing/test_message_content_codec.py`: спецификация для image placeholder, unknown type marker, text-only embedding и prefix preserving attachments; использовалась как source evidence, тесты здесь **не запускались**.

**Parity fixtures:** сообщение только-текст; text + `image_url`; image-only; неизвестный `tool_result`; несколько `text`; data URI, локальный URI, удалённый HTTP; восстановление detail/display_role; prepend+append без потери media. Провести эти fixtures отдельно на future Rust content model и на границах каждого LLM-provider/GUI/history/RAG consumer.

## Что не решено этим аудитом

Не выполнена реальная image-upload validation, полный инвентарь будущих типов modality/LLM provider chunks, fixture Unicode/blob large storage и проверка Unity-создателя изображений. Они остаются за дополнительным integration audit; их отсутствие не означает, что новая версия может игнорировать media.
