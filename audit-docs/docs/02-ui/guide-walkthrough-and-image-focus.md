# Guide: walkthrough, уровни, интерактивные снимки и переход в Wiki

**Capability IDs:** `CAP-UI-GUIDE-001—006`. **Статус:** `ACTIVE` для зарегистрированного Guide Dialog, `CONDITIONAL` для перехода в Wiki (нужен callback), для конкретного image target (нужны assets и предопределённая карта). **Source:** Python source snapshot `CodeNow.zip`, исследован 2026-10-30. Методы и строки ниже — evidence; поведение Qt в GUI-тесте не воспроизведено.

## Назначение и пользовательские сценарии

NeuroMita предоставляет отдельное немодальное окно пошагового руководства (`src/ui/windows/guide_dialog.py:14-63`) для базовой настройки LLM, голоса, памяти, экранного/камерного ввода, моделей и Sandbox. Это **не** только статическая справка: пользователь выбирает уровень детализации, язык, страницу/раздел, кликает на номер шага текстового описания, а GUI выделяет соответствующую область иллюстрации (`src/ui/widgets/guide_widget.py:77-173,793-984,1137-1184`). Часть страниц может открывать связанную статью локальной Wiki через callback (`guide_dialog.py:51-66`).

`GuideDialog` — отдельное окно, не страница в основном layout. Оно `setModal(False)`, создаёт `GuideWidget`, подписывается на `closed`, перед показом вызывает `start()` для возврата к первой доступной странице; геометрия рассчитывается от текущего экрана с ограничением размера (`src/ui/windows/guide_dialog.py:17-85`). Callback перехода в Wiki устанавливается `apply_payload`, а `_open_wiki` сначала скрывает окно (`hide`), потом вызывает callback; если callback отсутствует, переход не производится (`:50-67`). Жизненный цикл Guide window задаёт внешний WindowManager: наличие этого класса не доказывает способ регистрации/показ в каждом launch mode.

## Pages, фильтрация и сохранённые настройки

`GuideWidget.__init__` берёт `GUIDE_LEVEL` из settings (`basic`, `advanced`, `full`), а при отсутствии валидного значения вычисляет уровень из `INTERFACE_MODE` через `normalize_mode`. Язык инициализируется из `LANGUAGE` (default `RU`); собственный `current_language` хранится в виджете (`src/ui/widgets/guide_widget.py:174-208`). При смене уровня вызывается `set_setting(self, "GUIDE_LEVEL", level)`, а при ошибке — warning, не падение GUI (`:928-962`). При смене языка UI пересоздаёт подписи и progress steps, затем перерисовывает текущую страницу (`:701-713`). Смена языка в этом обработчике не вызывает явный `set_setting(LANGUAGE)`; это **локальный** выбор для Guide на данной ветке, независимо от глобальной language preference.

Конструктор `_init_pages` задаёт 13 последовательных страниц (`:969-987`): Welcome, Preset, Voiceover, Microphone, Memory RAG, Memory Vector, Memory Graph, Screen Capture, Camera, Camera Dependencies, Models, Sandbox, Final. По `min_mode` реально доступны: `basic` — Welcome/Preset/Final (3); `advanced` добавляет Voiceover/Microphone (5); `full` — все 13 (`:1248,1278,1313,1383,1568-1875`). Исторические `MemoryGuidePage`/`ScreenAnalysisGuidePage` определены рядом (`:1427-1565`), но **не включены в `_init_pages`**, поэтому их наличие в source само по себе не означает active page. Такой же принцип нужен при переносе функционала: фактически доступные сценарии определяет регистрация, а не наличие типа.

При переключении уровня `_on_level_changed` старается сохранить текущую страницу, если она остаётся доступна; иначе возвращается на ближайшую предшествующую оставшуюся страницу, либо на первую (`:928-961`). Навигация prev/next ограничена границами отфильтрованного набора, прогресс показывает `index+1 / len(filtered)`; повторное открытие guide сбрасывает текущую страницу через `start()` (`:1189-1240`).

## Интерактивные иллюстрации

Каждая страница реализует контракт `IGuidePage`: RU/EN заголовок и описание, имя изображения; опционально crop и Wiki target (`src/ui/widgets/guide_widget.py:15-48`). Картинка ищется по относительному `assets/<filename>` на основании **текущей рабочей директории**, а не строго заданного application resource root (`:987-1002`). Если файл отсутствует или Qt не декодирует его, пользователь видит `Изображение не загружено`/`Image not loaded`, однако текст и навигация остаются доступны (`:1189-1228`). При развёртывании и смене cwd необходим parity test поиска assets.

`_format_description` преобразует фрагменты вида `<b>ЧИСЛО ...</b>` в ссылки `guide-step:N`; сопоставление не делается по произвольному `N` в тексте (`:1003-1038`). `_STEP_TARGETS` задаёт вручную нормализованные прямоугольники изображения **по class-name страницы и номеру шага**, а `GuideImageLabel.paintEvent` рисует полупрозрачный focus rectangle поверх изображения (`:50-174`). Hover по ссылке временно показывает focus, click фиксирует фокус, увеличивает zoom до `>=1.35` и прокручивает screenshot к target (`:1137-1179`). Номера, отсутствующие в `_STEP_TARGETS`, не вызывают focal scroll и не должны считаться actionable. При открытии другой страницы фокус и pinned step очищаются (`:1194-1202`).

Картинка может иметь нормализованный crop страницы. Доступны Fit, Width, Actual Size, zoom out/in с внутренним zoom-factor от 1 до 6 относительно fitted-size; при resize вызывается rescale (`:1039-1136,1184-1188`). `actual size` вычисляется через отношение original pixmap к fitted pixmap, но ограничивается внутренним диапазоном, поэтому на маленьких viewport **не всегда означает точно 100% исходных пикселей**. Процент показывается от фактической ширины scaled/original (`:1120-1135`). UI default image zoom обновляется при переходе между страницами.

## Progress и выход к справке

`_page_section_key` отображает 13 pages в 6 функциональных разделов (start/voice/memory/vision/tools/finish); это presentation metadata, а не composition root сервисов. `_rebuild_progress_steps` создаёт кликабельные сегменты, tab раздела и menu contents с быстрым переходом; состояния `done/current/upcoming` вычисляются из текущего индекса (`:790-925`). Нет отдельного долговременного storage последней достигнутой страницы — в исследованном пути хранится только выбранный уровень.

Кнопка Help показывается только если текущий `IGuidePage.get_wiki_target()` непустой и callback callable. `GuideWidget._open_help` передаёт этот target; `GuideDialog._open_wiki` скрывает диалог и вызывает предоставленный callback (`guide_widget.py:1181-1183,1222-1227`, `guide_dialog.py:59-66`). Целевой маршрут локальной Wiki описан в [wiki-navigation-localization-and-anchors.md](wiki-navigation-localization-and-anchors.md); Guide **не** загружает статью самостоятельно.

## Контракты для переписывания с нуля

- `REQ-UI-GUIDE-002`: пользовательские уровни `basic/advanced/full`; валидный saved preference, fallback от interface mode; изменение уровня, непрерывная навигация при сокращении списка и сохранение значения.
- `REQ-UI-GUIDE-003`: 13 действительно зарегистрированных страниц с условными наборами 3/5/13; RU/EN текст; независимая смена языка внутри Guide; placeholders при отсутствующих assets. Переход на новую UI-технологию не должен требовать копировать классы `IGuidePage`.
- `REQ-UI-GUIDE-004`: interactive numbered steps с декларативной картой привязок screenshot regions; hover/pin/zoom/scroll, reset на переходе, обработка отсутствующего image/target.
- `REQ-UI-GUIDE-005`: независимое guide window, ограничение геометрии экраном, contents/section progress, back/next, restart на reopen, корректный cancel/close, wiki deep link только при валидном callback.
- `REQ-UI-GUIDE-006`: packaging resource paths устойчивы к иному cwd, отсутствующим языковым images, crop bounds, high-DPI, локализации и разрешениям; при отсутствии изображения не ломается текстовая навигация.

Для новой Core архитектуры это **presentation functionality**. Выбор Slint/QML не выполняется в этом исследовании, модель хранения страниц и screenshot targets пока только вариант без решения.

## Проверки и вопросы

Предлагаемые, **не исполненные** проверки: `basic/advanced/full` и изменение уровня на скрытой странице; смена RU/EN при открытом шаге; direct click номер 1 и отсутствующий номер; drag/resize/zoom; absence of asset при другом cwd; Wiki callback absent/present and hide-before-open; repeated close/reopen; DPI scale и viewport < минимального размера иллюстрации. Отдельно проверить, в каких реальных launch modes регистрируется GuideDialog, и ведёт ли external WindowManager persistent dialogue instance. Не считать старые helper page classes активными без proof of registration.
