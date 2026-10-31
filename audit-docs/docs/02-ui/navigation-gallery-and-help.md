# Навигация, галерея, новости, справка и логи

**Capabilities:** CAP-UI-NAV-001, CAP-GALLERY-001, CAP-NEWS-001, CAP-HELP-001/002, CAP-LOGS-001. **Статус:** ACTIVE GUI functions; удалённая лента и наличие локальных artifacts условны. Это функциональные требования к desktop core, не выбор будущего toolkit.

## Навигация и настройки

MainPageRegistry регистрирует7 страниц: home, news, gallery, sandbox, settings, wiki, logs. Главная создаётся сразу; sandbox/news/gallery/wiki/logs при первом посещении показывают placeholder и строятся через отложенный Qt callback. Settings может предварительно создаваться по setting. Activation/deactivation вызывается при переключении; действия для ещё неготовой страницы копятся до её создания. Ошибка построения оставляет видимый failed placeholder; повторная recovery UI политика отдельно не подтверждена.

Settings registry содержит general/language/api/characters/voice/microphone/ai_engine/game/models/screen/updates/data_collection. Sections имеют labels/builders/min_mode и lazy feature preparation. General/language всегда доступны; остальные могут скрываться отдельным SECTION_*_ENABLED. Defaults дают basic sections и updates; legacy developer visibility мигрируется в data_collection. Скрытый раздел и выключенная runtime capability — разные состояния. Deep link может открыть category/subsection с force.

SettingsPageViewModel готовит imports/data в worker, ждёт readiness backend при необходимости, загружает runtime features, а optional GUI controllers создаёт в Qt callback. Следовательно будущая UI спецификация должна сохранять loading/error/retry/readiness semantics, не только набор checkbox. Часть settings построения исследована; содержание всех разделов ещё не объявлено завершённым.

WindowCompositionController регистрирует ai_hub, voice_models, asr_glossary, guide как singleton/hide-on-close; vc_redist и triton dependencies — modal temporary dialogs. Installation progress window умеет скрываться и открываться из sidebar. Полный менеджер всех прочих ad-hoc dialogs и их lifecycle ещё проверяется отдельно; эта регистрация не является полным списком окон.

## Галерея

Python читает {Unity install directory}/Gallery, а не Images из истории чата. Поддерживаются png/jpg/jpeg/webp/bmp, только непосредственно внутри каталога. Timestamp извлекается из selfie_YYYYMMDD_HHMMSSmmm; иначе используется mtime и пометка неизвестного capture time. Сортировка по времени/имени, пользователь выбирает сначала новые/старые. Нет анализа изображений моделью на этой странице.

Scan выполняется асинхронно; QFileSystemWatcher следит за существующим Gallery/родительскими каталогами, события дебаунсятся250 ms, refresh выполняется при активности страницы. Пусто/загрузка/ошибка/фотографии — разные UI states. Открытие папки создаёт Gallery при возможности и передаёт path ОС.

Thumbnails запрашиваются по потребности, объединяются по cache_key(path,mtime_ns,size), читаются пачками до12 с QImageReader, auto-transform и уменьшением до640×420. Это не нейросетевая функция. Viewer открывается один на страницу: previous/next, arrows, fit, wheel zoom0.03—12, drag/pan, metadata/date/size/dimensions, открытие оригинала системным приложением. Последний photo request имеет latest semantics, viewer проверяет принадлежность эффекта текущему photo. Удаление/редактирование/загрузка в облако в просмотренном flow не найдены.

## Новости

Home и news используют релизную ленту выбранного update contour. NewsReleasesStore кеширует release data/cards; async helper объединяет inflight callbacks. Источник — release catalog manifest с GitHub API fallback, затем фильтрация подходящих launcher assets. Offline/error даёт пустой cache и видимое сообщение, force refresh сбрасывает cache. Это сетевое чтение, не отдельная локальная база новостей.

Release body преобразуется в summary/cards и полную content projection; GUI может открыть конкретный release. Детальная страница/карточки и ссылки ещё не полностью исследованы, поэтому полный Markdown UX не заявляется. Смена repository очищает кеш, но get_news_releases записывает result после запроса без проверки неизменности repository: старый result может попасть в store после смены contour. Это stale-result риск, не необходимость сохранять текущий cache design.

## Wiki и руководство

Wiki — локальные docs/wiki/{language}/*.md, QTextDocument Markdown → HTML → QTextBrowser; собственного встроенного web browser для этого не требуется. Есть home cards/categories, article view, anchors, back/forward history и reload. Markdown headers получают anchors, сгенерированные с обработкой повторов. UI language выбирает docs language, fallback en; смена языка перечитывает текущую относительную страницу/anchor без добавления history entry.

Внутренние Markdown links остаются внутри wiki root с resolve/containment checks; http/https открывает ОС browser. app: links ведут на страницу/настройку и section query; home cards имеют такие же переходы. Это часть product navigation contract. Синхронное чтение локального документа на UI thread видно в источнике; performance на больших статьях не измерялась.

GuideDialog — отдельное немодальное окно, step pages с изображением, заголовком/описанием, previous/next/progress и Help переходом к связанной wiki статье. При переходе к wiki окно скрывается. Показываемые страницы зависят от режима интерфейса; язык и изображения локальны. Начало/переоткрытие вызывает start→первый шаг. Image scaling/zoom/hotspot helpers найдены и частично просмотрены, полный guide interaction QA не выполнен.

## Логи

LogsPageViewModel асинхронно читает tail runtime_log_path, до64 KiB/500 lines, UTF-8 replacement, отбрасывает возможную оборванную первую строку. Отсутствующий файл и ошибка читаются как различимые сообщения. Есть refresh и открыть logs directory; последнее через os.startfile, Windows-specific. Это просмотр файлового tail, не доказанный structured search/export/continuous subscriber. Общий logging pipeline, privacy/redaction и все остальные diagnostics требуют отдельного прохода.

## Требования для новой реализации и пределы

Страницы должны оставаться доступны независимо от загрузки тяжёлых optional сервисов там, где их действия этого не требуют. Для filesystem/network jobs нужны явные loading/empty/error, source revision/identity, согласованный close и latest/coalesced policy. Local wiki, фото decode/thumbnail, OS integration и log tail необходимо оценивать при сравнении GUI candidates по функциям; существующие Qt types не являются единственным возможным способом.

Источники: main_page_registry, MainWindowCoordinator initialization/build/navigation/deep link; settings section_registry/access; SettingsPageViewModel по preparation; WindowCompositionController registration/factories/install progress; GalleryPage/ViewModel/PhotoGallery/Viewer по interaction paths; NewsPageViewModel/NewsReleasesStore/loading/cards; WikiPage render/path/links/history/locale; GuideDialog и GuideWidget step navigation; LogsPageViewModel. Остальные UI states/layout details, home updater, sandbox diagnostics и fine-tune data рассматриваются далее. Реальные окна, системные приложения и сетевые запросы не запускались.
