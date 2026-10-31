# Изображения, экран и веб-камера: функции Python

**Capabilities:** CAP-IMAGE-001—006. **Статус:** CONDITIONAL, кроме доступности самих GUI controls. Исследована Python-часть; реализация виртуальных камер и рисования в Unity отложена по запросу пользователя. Наличие checkbox не приравнивается к работающей функции.

## Пользовательские сценарии

| ID | Возможность | Фактический путь |
|---|---|---|
| CAP-IMAGE-001 | Прикрепить изображения к сообщению, отправить без текста, очистить вложения | ChatPanelViewModel stage files/image → staged state → AppShellController.send_message → ChatController |
| CAP-IMAGE-002 | Снять экран один раз или прикладывать его к каждой отправке | CaptureService.capture_screen → последние буферные кадры либо one-shot; AUTO_ATTACH_IMAGES работает и без фонового захвата |
| CAP-IMAGE-003 | Непрерывно собирать историю экрана и инициировать диалог по таймеру | ScreenCapture JPEG ring history → CaptureController.send_interval_image → send_periodic_image_request |
| CAP-IMAGE-004 | Выбрать веб-камеру и прикладывать последние кадры | SettingsRuntimeOptionsViewModel enumeration/selection → CameraCapture → send_message camera_frames |
| CAP-IMAGE-005 | Передать картинку vision-модели либо предварительно описать её отдельным провайдером | ModelController image preprocessing, ImageDescriptionHandler; inline description для ответа основной модели |
| CAP-IMAGE-006 | Хранить картинки и описания, показывать историю, находить и удалять сироты | ConversationEventWriter → HistoryManager/Images; image_cleanup; settings actions |

Принимаемые от игрового клиента изображения имеют отдельные source/event_type: восприятие глазами персонажа, рисунок на мольберте, наблюдение за ТВ. Python использует их для смыслового контекста и роли показа; источник не сводится к безымянному массиву bytes. Рисунки дополнительно сохраняются в Drawings. Детали получения этих кадров клиентом не входят в текущий проход.

## Доступность и управление

Optional feature capture создаётся при ENABLE_IMAGE_ANALYSIS и хотя бы одном из ENABLE_SCREEN_ANALYSIS / ENABLE_CAMERA_CAPTURE / AUTO_ATTACH_IMAGES. Само отображение кнопки «снять экран» не создаёт CaptureService: при отсутствии сервиса UI получает пустой результат. Показанный в settings default master switch и fallback defaults разных runtime-ветвей следует различать: controller startup проверяет default False, one-shot и окончательная сборка сообщения — default True.

Настройки экрана: интервал, JPEG quality, FPS, history/transfer limits, максимальные размеры, исключение окна приложения либо окна по заголовку. ScreenCapture фактически использует interval_seconds с минимумом 0.5 s; FPS сохраняется и логируется, но не задаёт частоту цикла. Захватывается monitors[1] MSS при наличии, иначе monitors[0]; выбора произвольного монитора в прочитанном backend нет. Pillow thumbnail сохраняет пропорции и вписывает кадр в заданные размеры. Исключение окна — закрашивание прямоугольника чёрным после снимка, перед уменьшением/JPEG; при ошибке получения окна кадр продолжает обрабатываться.

Камера: enumeration пробует индексы0—4 через CAP_DSHOW, выбранное имя Camera N сохраняет CAMERA_INDEX. Захват использует cv2.VideoCapture(index) с backend по умолчанию. Частота цикла определяется FPS. Установка camera resolution/FPS в устройстве закомментирована; отдельного resize в прочитанном цикле нет. Поэтому поля ширины/высоты камеры не доказывают получение кадров этого размера. CAMERA_CAPTURE_INTERVAL считывается controller, но не передаётся backend. Camera-specific параметры и CAMERA_INDEX отсутствуют в _SETTING_KEYS CaptureController, кроме ENABLE_CAMERA_CAPTURE: живой перезапуск при их изменении этим subscription не реализован.

## Отправка и описание

Файловое прикрепление проверяет расширение png/jpg/jpeg/webp/bmp/gif, максимум8 файлов за одну операцию,32 MiB на файл и64 MiB суммарно за эту операцию. Проверяется изменение размера при чтении; декодирование содержимого как изображения здесь отсутствует. Повторные staging операции и clipboard имеют другой путь, поэтому эти пределы нельзя объявить общим лимитом сообщения.

AppShellController получает кадры асинхронно, объединяет explicit → screen → staged → camera, выполняет dedupe и master-switch filter. Допускается image-only turn; GUI показывает исходящее сообщение, затем отправляется обычное событие SEND_MESSAGE. Staged attachments очищаются после публикации события, до успешной генерации. В этой ветви data URL маркируется image/jpeg независимо от исходного расширения прикреплённого файла; это не преобразование PNG/GIF в JPEG.

Non-native режим выбирается setting IMAGE_DESCRIPTION_ENABLED, а не обязательной проверкой реальной vision-способности основной модели. Один кадр описывается отдельно; несколько отправляются одним вызовом как последовательная сцена. Выбирается отдельный API preset по id/имени либо текущий. Detail brief/normal/detailed задаёт prompt; source hint отличает ТВ, глаза персонажа и рисунок. Описание входит в скрытый текстовый контекст, исходные картинки убираются из текущего запроса основной модели, но сохраняются для истории. Ошибки handler превращает в placeholders; последовательность с placeholder не получает обычного scene context. Полной отдельной отмены/бюджета этого вспомогательного вызова в handler не обнаружено; транспортные ограничения провайдера исследуются отдельно.

Inline режим просит основную модель заполнить image_description в structured response либо скрытый XML block в plain response. Block извлекается из видимой plain-реплики. Для истории сохраняется словарь описаний по детализации; UI при чтении предпочитает manual → detailed → normal → brief. Наличие описания не удаляет image artifact: HistoryManager всё равно восстанавливает image parts из файлов. Комментарий про полную замену изображения описанием сам по себе не доказывает такую замену во всех последующих prompt paths.

## Хранение и обслуживание

Изображения из data URL пишутся в Histories/{storage_name}/Images; имя — SHA256 очищенной base64-строки с расширением. Повторное сохранение использует существующий файл/cache. SQLite metadata содержит multimodal_parts и image_descriptions. При read локальные paths снова превращаются в data URL; неизвестные типы частей MessageContentCodec сохраняет, а не выбрасывает. Файловый artifact и DB reference не составляют одну транзакцию.

Рисунки дополнительно сохраняются как Drawings/drawing_{timestamp_seconds}_{index}.jpg. Cleanup utility обходит только */Images и фиксированный world.db, собирает references из metadata, сопоставляет normcase paths, поддерживает scan/stats/delete и dry_run. UI предоставляет просмотр статистики, поиск и удаление сирот. При ошибке чтения DB utility логирует исключение и возвращает неполный набор references, поэтому результат сканирования нельзя безусловно считать достоверным разрешением на удаление.

Настройки IMAGE_CLEANUP_TTL_ENABLED/DAYS/MAX_PER_CHAR объявлены в GUI. По поиску по Python src их runtime-потребитель не найден: автоматическое удаление по возрасту/числу пока UNRESOLVED/не подтверждено. Это не то же самое, что действующая ручная очистка сирот.

HistoryController умеет уменьшать качество изображений в подготовленной истории: start index абсолютный либо процент длины, quality уменьшается по индексу с нижней границей; сообщения с описанием пропускаются. Изменяется собранная projection для запроса, не исходные файлы. Фактический порядок сообщений и ожидаемое понятие «старые» нужно согласовать отдельно, не копировать формулу автоматически.

## Наблюдения и требования к новой реализации

- Кадр должен иметь источник, время захвата, формат и размеры. Отдельные лимиты нужны на acquisition buffer, staging и готовый запрос; не требуется копировать текущие Python containers/classes.
- Нужны самостоятельные сценарии manual attach / one-shot / background capture / scheduled dialogue; включение одного не должно случайно определять доступность другого.
- Readiness устройства, работающий capture loop, наличие свежего кадра и активный checkbox — разные состояния. Controller выставляет active после start_capture без подтверждения первого кадра и может показывать активность после backend failure.
- Оригинал, сжатая projection, описание и permanent drawing имеют разный lifecycle. Удаление требует успешного чтения references и координации с записью/чтением artifacts.
- CameraCapture.stop_capture делает join без timeout; ошибка чтения кадра делает continue до sleep, а error_count сбрасывается перед каждой попыткой. Эти особенности не нужны новой функциональной спецификации.
- Кнопка ручного screenshot имеет отдельный дефект преобразования: ChatPanelViewModel._capture_screen итерирует frames[0] как sequence of frames, хотя CaptureService возвращает list[bytes]. Это превращает отдельные byte values через bytes(int), вместо staging целого JPEG. Статический вывод; реальный захват не запускался.

## Зависимости и граница Rust

В этой группе core Python использует MSS для desktop capture, Pillow для resize/JPEG, OpenCV для webcam enumeration/capture/JPEG, pywin32 для окна; threading/base64/hashlib/SQLite — инфраструктура. OpenCV оформлен как optional managed dependency с --no-deps, не является AI inference. MSS импортируется runtime, хотя в корневом requirements.txt его нет: один этот файл не исчерпывает зависимости. ImageDescriptionHandler использует общий LLM API orchestration, не локальный vision inference. Выбор Rust crates и актуальных platform backends требует отдельного исследования первичных источников; отсутствие прямого package-name аналога не является блокером функции.

## Доказательства и пределы

Прочитаны CaptureController целиком; ScreenCapture start/loop/history/one-shot/exclusion; CameraCapture целиком; ImageDescriptionHandler целиком; AppShellController send/capture; ChatPanelViewModel dispatch/staging/screenshot; SettingsRuntimeOptionsViewModel целиком; screen_analysis_settings основные sections и cleanup actions; HistoryManager image save/read/description restore; ConversationEventWriter incoming image metadata и drawings save; image_cleanup целиком; HistoryController quality-reduction ветвь; OpenCVInstallableComponent. Test_send_message_capture прочитан частично как дополнительное доказательство service contract, не запускался. Никаких screenshots, доступа к камере, запросов vision API, удаления картинок или открытия пользовательской DB не выполнялось. Media editing UI исследуется в GUI-проходе.
