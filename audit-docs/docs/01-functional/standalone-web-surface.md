# Отдельная web/VTT и mock API поверхность

**Capability:** CAP-WEB-001/002. **Статус:** standalone/EXPERIMENTAL, автоматический запуск из обычного core не подтверждён. Это не TCP game server и не основной SpeechController.

src/web/server.py содержит FastAPI app с root_path=/api, OpenAPI docs/redoc, VTT router и отдельным __main__ запуском uvicorn на0.0.0.0:8000. По поиску src/controllers/startup и launch/build/scripts не найдено его запуска обычным lifecycle. Значит uvicorn в requirements и web directory не доказывают обязательный HTTP server у desktop приложения. Запуск через внешний uvicorn command остаётся возможным standalone entry, а не найденной GUI function.

CAP-WEB-001: GET /vtt/models перечисляет содержимое web/vtt/models относительно cwd; POST /vtt/transcribe принимает model_name и upload, проверяет MIME audio/wav, декодирует soundfile, переписывает WAV в памяти, требует mono/16-bit/uncompressed и запускает Vosk KaldiRecognizer. Модель создаётся заново в каждом service instance. Ответ text/time_elapsed. Это inference, который по исходному решению остаётся Python, если эта отдельная API функция нужна.

Ограничения источника: имя модели проверяется существованием составленного path, не отдельной containment policy; upload целиком читается в память; при первом AcceptWaveform=True loop прерывается и возвращает rec.Result, а не полный FinalResult всего файла. Эти признаки не дают основания считать endpoint эквивалентом текущего live ASR pipeline. Аутентификация и app-level upload size limit в прочитанных router/dependencies не обнаружены. Сервер не запускался и доступность endpoint не проверялась.

CAP-WEB-002: при NEUROMITA_ENABLE_MOCK_API=1 добавляется /mock/openai/v1 с info, models и chat/completions. Можно задать scenario/status/message/error_code, вернуть mock model list либо готовый chat payload с optional reasoning и usage. Это тестовая поверхность обработки API ошибок; по умолчанию выключена. Возвращается один JSON response; streaming simulation в прочитанном router не реализована. FastAPI/Vosk/loguru этой программы не должны автоматически считаться обязательными core dependencies без отдельного требования сохранить standalone API.

Источники: server.py, оба routers и services, VTT schemas/dependencies/consts и web utils прочитаны. Production entry search выполнен отдельно. Файлы моделей, uploads, сокеты и пользовательская DB не открывались. Решение сохранить/объединить/удалить standalone функцию — design input, не принятое архитектурное решение.
