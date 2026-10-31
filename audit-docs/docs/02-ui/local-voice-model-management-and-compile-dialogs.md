# Локальные голосовые модели: пользовательский сценарий управления и загрузки

**Область:** UI/voice installables, `CONDITIONAL` (локальная озвучка и отдельные диалоги). **Ревизия evidence:** Python `releases`, исходники CodeNow (2026-10-30). **Границы:** функциональные требования, а не перенос существующего QWidget в Rust.

## Назначение и точки входа

Пользователь может открыть каталог локальных моделей голоса, увидеть доступные модели и зависимости, выбрать модель, проверить характеристики устройства (GPU/VRAM, языки, ограничения), установить либо удалить веса и окружение, изменить модельные параметры, запросить справку и сохранить результат. Регистрация окна `voice_models` выполняется в `src/controllers/gui/window_composition_controller.py:25-79` как отдельный диалог с повторным использованием; рабочие команды отражены в типизированных `VoiceModelsState`/`UiIntent` в `src/ui/windows/voice_model_presentation.py:9-64`. Подключение VM и событий: `src/controllers/gui/voice_model_controller.py:15-152`, `src/controllers/gui/voice_models_view_model.py:22-153`.

**Поток:** open window → `RefreshVoiceModels` → асинхронный snapshot моделей/installed/dependencies → выделение карточки → модельная форма параметров → `SaveVoiceSettings` или `InstallVoiceModel`/`UninstallVoiceModel` → preflight/confirmation → background installable operation → progress/logs → `Events.Audio.REFRESH_VOICE_MODULES` и обновление доступных вариантов голоса в интерфейсе. Закрытие окна и сохранение параметров представлены разными намерениями; current controller `_on_close_dialog` вызывает save, затем close, см. `voice_model_controller.py:296-346`.

## Отображаемые данные и состояния

`VoiceModelsState`: `models`, `installed_models`, `dependencies_status`, `loading`, `operation`, `operation_model_id`, `error`, `revision`. `ModelDetailView` показывает метаданные выбранной модели, профиль, предупреждение, поддерживаемые языки, устройство и форму settings; `installed_models` влияет на видимость Install/Uninstall. Источники: `src/ui/windows/voice_model_view.py:35-236`, `voice_model_presentation.py:9-18`. Отдельно различаются **вес установлен**, **runtime-модель инициализирована**, **установочный backend доступен**, **пользовательская модель выбрана**; интерфейс не должен сворачивать всё в один флаг.

VM использует `IntentViewModel.run_latest` для асинхронного обновления снимка: устаревший результат предыдущего refresh не публикуется как актуальный (`src/controllers/gui/voice_models_view_model.py:104-153`; `src/controllers/gui/intent_view_model.py:114-165`). Progress операций приходит событиями `INSTALL_*`/`UNINSTALL_*`; после удачного окончания VM обновляет snapshot, а controller инициирует перечитывание voice modules (`voice_model_controller.py:260-288,343-378`). Временный `loading` презентации не тождественен загрузке модели в GPU.

## Установка, удаление и preflight

Перед install `backend.get_install_preflight(model_id)` может заблокировать операцию с объяснением или потребовать явного подтверждения отсутствующего backend. Только после принятия вызывается `start_install(model_id, with_ui, timeout_sec)` (`voice_model_controller.py:152-201`). Uninstall проверяет, не инициализирована ли модель (`LocalVoiceService.check_initialized(..., probe_worker=True)`), отказывает при активном использовании, затем спрашивает подтверждение необратимого удаления и вызывает `start_uninstall` (`:203-258`). Это пользовательские контракты, а не решение о конкретной реализации установщика. Реальные планы/зависимости: [installable catalog](../01-functional/installable-catalog-and-runtime-readiness-matrix.md), [component plans](../01-functional/installer-component-plans.md).

Параметры модели собираются со всех секций и передаются в backend `save_settings_values`, который возвращает ошибки по `model_id/field`; они показываются пользователю, а не просто игнорируются (`voice_model_controller.py:296-340`). Ошибки недоступного устройства имеют отдельный visible error. Использование настройки без установки модели — иной сценарий, чем активация модели для синтеза.

## Прогресс и системные диалоги

`VoiceInstallationWindow` и `VoiceActionWindow` — отдельные интерфейсы лога операции: визуальный progress, статус, время, блоки логов, raw log, copy/save log, очистка **экрана** лога без удаления runtime state. Присутствует индикация размеров, скорости, свободного диска и частоты обновлений (`src/ui/windows/voice_action_windows.py:35-680,684-940`). Это UI-презентация уже запущенной установки: скрытие/закрытие диалога не следует трактовать как автоматический rollback или уничтожение worker. Точная cancellation/queue contract зависит от общего installer manager.

Для ошибочного импорта нативной Triton DLL имеется `VCRedistWarningDialog` с действиями «открыть документацию», «повторить», «закрыть» (`voice_action_windows.py:940-1015`). Для Fish Speech+ компиляция CUDA kernels может выполняться на первом использовании или заранее по желанию. `TritonDependenciesDialog` показывает Windows long paths и позволяет включить их, открыть документацию, отложить compile либо явно подтвердить «компилировать сейчас» (checkbox), `:1017-1169`. Это **не обязательный запуск компиляции при любой установке**. Сходный compile/delete-cache workflow есть в AI Hub, см. [AI Hub](ai-hub.md).

## Взаимодействия и границы

- **Локальные модели и облачные Fish Audio пресеты — разные функции.** Первые требуют локального inference worker и установки артефактов; вторые — HTTP credentials/voice ID и сетевого API ([remote voice](../01-functional/remote-voice-presets-and-character-routing.md)).
- **Голосовые модели и пакеты голосов персонажей — разные единицы установки.** Установленный engine не означает установленный voice asset и наоборот.
- **Окно настроек и реальное воспроизведение не владеют одними и теми же состояниями:** изменение параметров, worker readiness, фактический TTS synthesis/Unity playback имеют независимые результаты.
- Ошибки GPU/VC runtime и long-paths — пользовательски значимые состояния, но их текущая Qt-форма и Python classes не являются требованиями к архитектуре нового Core.

## Функциональный чеклист для последующего паритета

Открыть/закрыть окно и сохранить настройки; выбрана установленная/неустановленная модель; смена выбора во время refresh; preflight blocked/ask/accepted; отменённое подтверждение; install и uninstall started/completed/failed; запрет удаления активной модели; недоступное устройство; переход на другой голос после успешного обновления; copy/save сырого лога; post-install Fish compile now/later/clear; platform prerequisites и документация. Не утверждать готовность GPU worker по факту окончания download.

**Не проверено в этом проходе:** рендер реального Qt-диалога, нативная компиляция Triton на Windows, установка/удаление моделей, download network, CUDA device tests. Всё перечисленное — статическое source evidence.
