# Галерея Unity: файловая коллекция, список, thumbnails и просмотрщик

**Capability:** `CAP-UI-GALLERY-001` — `ACTIVE` для UI и локальных файлов; связь с реальным Unity-производителем снимков ранее документирована лишь по транспортному контракту. **Исследование:** статический срез Python из `CodeNow.zip` на 2026-10-30; интерактивные Qt-тесты и Unity не запускались.

## Назначение и источники

Пользователь открывает галерею фотографий, сделанных игровым телефоном; страница обнаруживает локальные изображения, сортирует их, подгружает thumbnails, показывает полноразмерный кадр, позволяет перейти к следующему/предыдущему и открыть исходный файл/каталог.

- `src/services/photo_gallery.py:11-70` — `GalleryPhoto`, правила directory/scan/metadata, сортировка и ensure directory.
- `src/ui/pages/gallery_presentation.py:9-45` — state/intents/effects.
- `src/controllers/gui/gallery_page_view_model.py:19-133` — background scan, latest photo request, очередь thumbnail jobs и close.
- `src/ui/pages/gallery_page.py:32-281` — действия пользователя, states, watcher, сортировка и modal viewer.
- `src/ui/widgets/gallery_grid.py:24-83,86-191` — data model, lazy thumbnail signal, bounded image cache, delegate и layout.
- `src/ui/dialogs/gallery_viewer.py:25-208` — viewer, navigation, full image load, zoom и keyboard.

## Данные и invariants

`PhotoGallery.directory(configured_unity_dir)` применяет `unity_install_dir(...) / "Gallery"`; настройка `UNITY_INSTALL_DIR` читается во ViewModel. `scan()` не рекурсивный: только файлы непосредственного каталога с расширениями `.png/.jpg/.jpeg/.webp/.bmp`, без исключения hidden-файлов по имени. Если каталога нет, возвращает пустую коллекцию. Удалившиеся в момент `stat()` файлы пропускаются, остальные IO-ошибки могут завершить scan exception (`photo_gallery.py:33-43`).

`GalleryPhoto` содержит path, дату, флаг распознавания времени, размер и `mtime_ns`. Если stem соответствует `selfie_YYYYMMDD_HHMMSSfff`, время читается из имени, иначе — из mtime файла. Сортировка убывающая по `(captured_at, path.name)`; reverse в UI даёт «сначала старые» (`photo_gallery.py:44-66`, `gallery_page.py:229-233`). Cache identity: `(Path, mtime_ns, size_bytes)`; этот ключ не является content hash и не гарантирует обнаружение изменения содержимого при идентичном stat.

## Сценарии и состояния

1. Переход на страницу (`on_activated:157-159`) вызывает `RefreshGallery`. ВМ вычисляет каталог из настроек; при изменении пути очищает очередь thumbnails и текущие photos; ставит `loading`, `revision`, запускает coalesced асинхронный scan (`gallery_page_view_model.py:43-72`). Деактивация отключает watcher-triggered refresh/timer, но сама по себе не вызывает `close` и не декларирует отмену уже выполняющегося scan (`gallery_page.py:161-167`).
2. Файловый watcher следит максимум за двумя существующими каталогами из `[Gallery, Gallery.parent, Gallery.parent.parent]`, с debounce 250 мс (`gallery_page.py:208-227,43-48`). Watcher активен при показе страницы; удаление/пересоздание Gallery и внешние файловые события требуют интеграционного теста.
3. Состояние страницы содержит photos/loading/error/revision/directory. Empty/loading/error и count обновляются отдельно, ошибки при наличии старых photos показываются поверх grid, а при пустом списке — в empty view (`gallery_page.py:169-208`). Смена сортировки — локальная операция, не повторный scan.
4. Thumbnail выдаётся по запросу модели при DecorationRole (`gallery_grid.py:44-63`). ВМ коалесцирует по cache_key, выбирает пакеты **до 12**, читает в background. `QImageReader.setAutoTransform(True)`, thumbnail downscale по размеру до **640×420**, если исходник больше порога (`gallery_page_view_model.py:19-29,95-128`). Модель кеширует максимум **160** entries с LRU (`gallery_grid.py:65-83`); ошибка чтения тоже сохраняется как negative cache. При смене каталога уже поставленные в работу thumbnails могут вернуться позднее, но модель проигнорирует cache_key, которого нет в новых rows.
5. Клик/activation grid открывает один `GalleryViewer` на страницу, следующий клик только активирует существующее окно (`gallery_page.py:252-269`). Viewer фиксирует **snapshot** текущего отсортированного списка, поэтому refresh grid во время открытия viewer не меняет его список (`gallery_viewer.py:70-79`). Навигация стрелками, кнопками prev/next, full image load и открытие оригинала через ОС. Асинхронный `run_latest("gallery-photo")`, а viewer отвергает delivery эффекта, если `effect.photo != self.photos[self.index]` (`gallery_page_view_model.py:83-92`, `gallery_viewer.py:155-188`). Zoom в интервале масштаба 0.03–12; fit после загрузки и при resize, если zoom вручную не изменялся (`gallery_viewer.py:38-64`).
6. Open folder вызывает `ensure_directory`, затем `QDesktopServices.openUrl(file:)` и refresh (`gallery_page_view_model.py:73-82`, `gallery_page.py:270-277`). `mkdir(exist_ok=True)` **не имеет `parents=True`**; если parent Unity installation отсутствует, это может завершиться ошибкой вместо открытия пути — сценарий требует теста (`photo_gallery.py:68-70`).

## Границы и ошибки

- Физическое удаление/редактирование исходных фотографий не является действием галереи; всё обнаруженное изменение происходит через внешний file watcher или refresh.
- `QImageReader` возвращает `QImage` + error string; сломанный image не должен ломать сканирование списка, но появляется error placeholder/label. Полный viewer не закрывается автоматически при decode failure (`gallery_viewer.py:175-188`).
- Синхронизация snapshot viewer с внешними удалениями файлов не гарантирована: при navigation уже удалённое фото останется в фиксированном списке и даст ошибку загрузки, пока диалог не переоткрыт.
- Нет подтверждения того, что watcher сигнализирует обо всех сетевых/нестандартных путях; future target должен определять polling/rescan reconciliation отдельно.

## Требования к новой реализации

- `REQ-UI-GALLERY-001`: каталог как независимо вычисляемый внешний source с установленным форматом файла, сортировкой, timestamp fallback и feature status по фактическому пути.
- `REQ-UI-GALLERY-002`: lazy thumbnail decoding с ограничением параллельной работы и кэша; refresh/смена каталога не должны применять устаревшие изображения к новой выборке.
- `REQ-UI-GALLERY-003`: работа с отсутствующим каталогом, ошибками stat/decode и удалением файлов без разрушения пользовательского UI.
- `REQ-UI-GALLERY-004`: предсказуемая навигация/zoom/full-image и сохранение provenance конкретного снимка при открытии ОС; явный lifetime viewer snapshot.

## Варианты переорганизации без закрепления Rust-архитектуры

С точки зрения домена есть **обзор файловой коллекции**, **загрузка изображений**, **проекция состояния представления** и **операции открытия в ОС**. Текущие QObject/ViewModel и event signals не являются предписанной формой реализации. Важно сохранить identity/version, bounded decoding, отмену устаревших запросов, а не конкретные классы.

## Открытые вопросы

Нужны E2E-тесты при переустановке Unity в другую директорию, сетевом диске, пачке более 160 фото, смене файла с прежними stat, пересоздании Gallery, и real Unity photo naming producer. Тесты статическим анализом не заменены.
