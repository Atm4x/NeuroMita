# Wiki: локальные Markdown, переходы, локализация и идентичность anchors

**Capability:** `CAP-UI-WIKI-001—003` — ACTIVE local help navigation, external browser links CONDITIONAL. Source `CodeNow.zip`, 2026-10-30. Guide Dialog boundary source проверен; UI-поведение шага, zoom и фильтрации подробно рассмотрено в [Guide Walkthrough](guide-walkthrough-and-image-focus.md).

## Функция

`src/ui/pages/wiki_page.py:38-41,70-149,223-529` строит домашние карточки, sidebar категорий, toolbar, Markdown article и internal/external links. Wiki root устанавливается из `NEUROMITA_BASE_DIR/docs/wiki` либо от расположения модуля (`:142-149`). Подразумеваемые каталоги `/en`, `/ru` и т.п. выбираются языком, fallback — английский (`:765-800`). Это локальная документация продукта, не external website и не AI inference.

## Навигация и состояния

- `_WikiLocation(path,anchor)` — history entry, back/forward поддерживают обрезку будущей ветки при новом переходе; home и reload самостоятельные действия (`wiki_page.py:136-140,544-669`). Смена языка выбирает относительный документ и anchor в новом каталоге **без push history** (`:825-855`). При отсутствии перевода пытается fallback на `en`, отображает ошибку, если нет и fallback.
- `app:`-scheme, включая `app:settings/<category>?section=<subsection>`, вызывает `PageActions.show_settings_category(force=True)` либо switch page; Home cards также используют app links (`:674-737`). Внешние `http/https` передаются `QDesktopServices.openUrl`, локальные Markdown links резолвятся относительно текущей папки, ограничены `resolve().relative_to(_WIKI_ROOT.resolve())` и суффиксом `.md` (`:738-821`). `#anchor` прокручивает текущую статью.
- `_open_location:601-635` читает Markdown как UTF-8 и превращает `QTextDocument.setMarkdown()` в HTML. Missing/bad file показывает error state, не меняя текущую историю. UI рендерит index page как home cards, остальные как article; `QTimer` инициирует scroll к anchor.
- `src/ui/windows/guide_dialog.py:14-85` — самостоятельное немодальное Guide окно, которое `prepare_for_show()` запускает с первого шага; переход в Wiki сначала `hide()` guide, затем вызывает предоставленный callback. Подробный контракт 13 зарегистрированных pages, screenshot focus/zoom и переключения уровней описан в [Guide Walkthrough](guide-walkthrough-and-image-focus.md).

## Конкретный риск русских Markdown headers

`_slugify_heading` (`wiki_page.py:160-173`) удаляет из заголовка всё, кроме ASCII `[a-z0-9\s-]`. Для `"Быстрый старт"` результат **пустой**, поэтому `_collect_heading_ids` пропускает заголовок (`:175-200`). `_markdown_to_html` затем берёт получившиеся anchor IDs по порядку и внедряет их в **каждый** HTML `<hN>` (`:203-220`). Отсюда возможны два последствия:

1. Заголовок полностью на кириллице не получает корректного bookmark anchor.
2. Если перед английским заголовком был русский пропущенный, следующий английский slug может быть назначен **не тому** HTML-заголовку из-за позиционного `next(heading_ids)`.

Это следует непосредственно из алгоритмов с воспроизведённой проверкой regex для кириллицы; точное поведение `QTextDocument` в конкретной статье ещё не воспроизведено, так что квалифицировать как **подтверждённый риск якорей**, не доказанный пользовательский incident. Требуется golden fixture RU/EN mixed headers, code fence, repeated headings, markdown-generated links and explicit ids.

## Прочие важные ограничения

- Cross-locale fallback path должен обеспечивать **root confinement**, но текущая `_resolve_start_path` проверяет membership к `_WIKI_ROOT`, а не обязательно к конкретному language-root (`:787-798`); для переданного `../` возможно попадание в другой язык *внутри* Wiki root. Это не выход за sandbox Wiki, но отдельная политика выбора locale/relative path.
- `_resolve_clicked_path` принимает только существующий `.md` внутри root (`:809-821`), а другие ресурсы (например, картинки) обслуживаются самим QTextDocument посредством base URL, поэтому безопасность file resource-loading/URL scheme должна быть протестирована отдельно; Python код просмотрщика не является полным доказательством запрета загрузки произвольного другого local asset.
- Так как чтение файла и Markdown→HTML выполняется непосредственно в UI path, huge-document latency возможна; performance не измерялась.

## Требования

- `REQ-UI-WIKI-001`: локальное дерево переведённых Markdown с явным fallback и проверенной нормализацией/ограничением внутренних путей; внешние ссылки обрабатываются отдельно.
- `REQ-UI-WIKI-002`: navigation history (back/forward, anchors, home, reload), app links/deep links в settings, locale switch без лишних history entries.
- `REQ-UI-WIKI-003`: Unicode-aware stable anchors, корректный order-association с HTML headings, repeated-heading disambiguation и отсутствие внедрения anchors в code fences.
- `REQ-UI-GUIDE-001`: independent Guide window with hide-before-wiki transition, step/language state; дополнительные требования уровня GUI описаны в [Guide Walkthrough](guide-walkthrough-and-image-focus.md).

## Следующие проверки

`ru` headings/anchor, mixed Cyrillic/English, same heading repeated, link to `app:settings`, path traversal inside/outside wiki root, missing translated doc and on-the-fly language change. Нужны offscreen Qt tests; нынешний обзор выполнен статически.
