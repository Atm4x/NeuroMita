# Реальные callsites динамических импортов и нативных загрузчиков (Pass 12)

**Метод:** AST производственных `.py` из `CodeNow.zip/src`, исключая только `src/utils/Testing/`. Это точные синтаксические вызовы `import_module`, `__import__`, `spec_from_file_location`, `WinDLL`, `CDLL`, `add_dll_directory` с выражением первого аргумента, **не** трасса runtime исполнений. Иные формы загрузки и вызовы через alias могут отсутствовать. Исходники не менялись.

- Найдено **24** вызовов в **18** файлах; классификация `{'import_module': 16, '__import__': 2, 'CDLL': 1, 'WinDLL': 5}`. AST parse errors: **0**.
- В `arg expression` выражение сохранено без вычисления: `module_name`, `normalized`, `f"{...}"` — динамические значения, их нельзя считать фиксированными пакетами.
- Отдельные voice/AI registry imports выполняются внутри Python worker или в conditional backend, а `ctypes.WinDLL` — внутри Windows API-интеграций. Для Rust Core важно функциональное владение и deployment, не идентичная Python import semantics.

| Source file:line | Import mechanism | First argument expression |
|---|---|---|
| `src/controllers/gui/presentation_hub.py:146` | `import_module` | `spec.builder_ref.partition(':')[0]` |
| `src/controllers/gui/presentation_hub.py:148` | `import_module` | `module_name` |
| `src/handlers/ai_engine/worker_process.py:270` | `import_module` | `normalized` |
| `src/handlers/asr_models/registry.py:28` | `import_module` | `module_name` |
| `src/handlers/camera_handler.py:42` | `__import__` | `'cv2'` |
| `src/handlers/llm_providers/__init__.py:18` | `import_module` | `module_name` |
| `src/handlers/screen_handler.py:56` | `__import__` | `'PIL.Image'` |
| `src/handlers/voice_models/edge_tts_rvc_model.py:594` | `import_module` | `module_name` |
| `src/handlers/voice_models/edge_tts_rvc_model.py:1323` | `import_module` | `f'{module_name}.lib.infer_pack.onnx_inference'` |
| `src/handlers/voice_models/edge_tts_rvc_model.py:1396` | `import_module` | `f'{module_name}.inference_onnx'` |
| `src/infrastructure/audio/windows_endpoint_identity.py:23` | `CDLL` | `path` |
| `src/infrastructure/audio/windows_endpoint_identity.py:34` | `WinDLL` | `'ole32'` |
| `src/installables/registry_builder.py:33` | `import_module` | `module_name` |
| `src/managers/provider_manager.py:36` | `import_module` | `module_name` |
| `src/managers/tools/builtin/__init__.py:18` | `import_module` | `module_name` |
| `src/managers/tools/dialects/registry.py:28` | `import_module` | `self._package` |
| `src/managers/tools/dialects/registry.py:41` | `import_module` | `full` |
| `src/managers/tools/tool_manager.py:37` | `import_module` | `self._module_name` |
| `src/services/hardware_inventory_service.py:79` | `WinDLL` | `'dxgi.dll'` |
| `src/services/hardware_inventory_service.py:146` | `WinDLL` | `'nvcuda.dll'` |
| `src/services/unity_process_guard.py:36` | `WinDLL` | `'user32'` |
| `src/ui/pages/main_page_registry.py:19` | `import_module` | `self.module_name` |
| `src/ui/pages/settings/section_registry.py:182` | `import_module` | `module_name` |
| `src/utils/native_paths.py:38` | `WinDLL` | `'kernel32'` |

## Пределы доказательства и следующая проверка

1. Сопоставить runtime reachability: composition-root registration, пользовательский выбор, conditional backend и AI worker bootstrap.
2. Сопоставить зависимость с `requirements.txt`, optional install plan и native DLL, не делать вывода «неиспользуемая» только по отсутствию `import`.
3. Некоторые вызовы `importlib` находятся внутри HTTP/network, GUI или voice model-specific ветвей и в обычном headless старте не исполняются.
4. Не заменять функциональную спецификацию списком callsites. См. [реестры](../04-dependencies/dynamic-import-registries-and-runtime-capability-contracts.md), [границы Core/AI](../04-dependencies/ai-worker-python-core-import-boundaries.md), [source→capability](../06-design-input/feature-traceability.md).
