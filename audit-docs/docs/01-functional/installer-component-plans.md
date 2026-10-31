# Компонентные планы установки: конкретные варианты voice и media

**Статус:** CONDITIONAL; доступность зависит от hardware/backend и модели. Продолжение общего [аудита установщика](installations.md). Проверены статически implementation plans, **не загружались веса, пакеты, архивы, GPU-компоненты и внешние лицензии**.

## Почему компонентные планы — отдельная функциональная область

Общая install queue не гарантирует одинаковый жизненный цикл каждой модели. Конкретный component plan определяет prerequisites, файлы, модельный backend, внешние инструменты, patching, compile, verification и destructive clean behavior. Поэтому для parity Rust host нельзя заменить всю установку абстрактным `pip install model`. Более того, Python execution/callback отдельных планов логично оставлять в AI management environment, пока не определён точный контракт: это **кандидат на границу**, не утверждённое архитектурное решение.

| Модель/компонент | Проверенный сценарий install plan | Источник |
|---|---|---|
| F5-TTS | Backend + language/variant; pip dependencies (включая NumPy `<2.0` constraint), подготовка директорий, HTTP weights, HTTP vocoder, optional RVC assets, final installed check; Python/RVC compatibility warning | `src/handlers/voice_models/f5_tts_model.py:300-426` |
| Fish Speech | Variant-specific backend, pip + model assets; optional RVC, для `medium+` / `medium+low` — Triton и optional compilation; для `medium+low` — TTS/RVC compatibility patch; final check | `src/handlers/voice_models/fish_speech_model.py:359-479` |
| OmniVoice | Backend check, pip dependencies, Hugging Face snapshot download через callback, final validation | `src/handlers/voice_models/omnivoice_model.py:160-214` |
| Edge TTS + RVC | Backend-specific CUDA/ONNX variants; pip, RVC runtime assets, conditional fairseq patch, TTS/RVC compatibility patch, final check | `src/handlers/voice_models/edge_tts_rvc_model.py:461-568` |
| FFmpeg | Download + media setup, reverse uninstall; существующий путь может дать уже установленный результат, а не запуск установки | `src/installables/ffmpeg_component.py:71-141` |
| OpenCV | `opencv` managed pip layer, already-installed detection по managed record либо runtime cv2; uninstall полагается на удаление immutable optional environment, а не ручную очистку main Lib | `src/installables/opencv_component.py:86-127` |

## Состояния и ключевые инварианты

- Plans возвращают `already_installed=True`/пустые actions при выполненном model-specific installed predicate. Но это не доказательство, что inference initialized; проверить `get_status`/`initialize` отдельно.
- Для F5/Fish отдельные RVC asset-ветки обусловлены выбранным model ID, поэтому нельзя считать, что все варианты требуют одинакового диска/пакетов.
- Для Fish optional compilation может не быть критерием установки, но должна быть отдельным результатом; не сводить «compile skipped» к «готово к максимальной производительности».
- План содержит `progress` и `progress_to` не как byte-grounded progress; UI не должен считать их весом модели/объёмом данных.
- Установочные проверки повторно используют `is_installed` и runtime context; часть valid-success statuses зависит от точного backend/device/asset state. Ссылка в карточке каталога не гарантирует доступность remote artifact.
- `clean` и изменение environment — разная семантика с обычным already-installed fast path. Нужны отдельные тесты partial download, optional compiler failure, Windows lock, GPU switching и crash между действиями.

## REQ-INSTALL-002 / validation

Каждая активная модель должна иметь проверяемые plan inputs (model id/backend/OS/paths), действие и cancellation boundary, artifact origin/size/checksum если доступен, finish predicate, rollback/recovery outcome, UI status. Внешние Python-пакеты модельной inference цепочки не следует автоматически делать прямыми зависимостями нового Rust Core. Потребуется отдельная матрица `component ID → runtime import → model assets → install steps → initialization readiness → uninstall ownership`. Настоящий документ фиксирует основные concrete plans, не утверждает их исчерпывающий аудит.

## Неисследованное

Прямые модели ASR, beat_this, RAG custom model plans и voice assets owner, download/checksum policy у сторонних Hugging Face snapshots, лицензии всех внешних пакетов, все uninstall-specific tails и новые model-specific error handlers. Данный проход не выполнял runtime tests.
