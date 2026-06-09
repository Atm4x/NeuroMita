import os

from core.events import get_event_bus, Events, Event
from main_logger import logger
from game_connections.race23 import BridgeClient, set_bridge_client


_PROMTS_ROOT = os.environ.get("NEUROMITA_PROMPTS_DIR", os.path.abspath("Prompts"))


def _read_prompt(relative_path):
    for root in (_PROMTS_ROOT, os.path.join(os.path.dirname(_PROMTS_ROOT), "extra", "Prompts")):
        path = os.path.join(root, relative_path)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    return ""


class Race23Controller:

    def __init__(self, settings):
        self.settings = settings
        self.event_bus = get_event_bus()
        self._enabled = False
        self._direct_lua_enabled = False
        self._postfix = "mita"

        self._init_bridge()
        self._load_settings()

        self.event_bus.subscribe(Events.Race23.GENERATE_ACTION, self._on_generate_action, weak=False)
        self.event_bus.subscribe(Events.Race23.BRIDGE_RESET, self._on_bridge_reset, weak=False)
        self.event_bus.subscribe(Events.Race23.BRIDGE_STATUS, self._on_bridge_status, weak=False)
        self.event_bus.subscribe(Events.Core.SETTING_CHANGED, self._on_setting_changed, weak=False)
        self.event_bus.subscribe(Events.Model.ON_SUCCESSFUL_RESPONSE, self._on_response_done, weak=False)
        self.event_bus.subscribe(Events.Model.ON_FAILED_RESPONSE, self._on_response_done, weak=False)

        if self._enabled:
            self._inject_system_prompt()
            self._sync_tool_settings()

        logger.info("[Race23] Controller initialised, enabled=%s, postfix=%r", self._enabled, self._postfix)

    def _init_bridge(self):
        custom_dir = str(self.settings.get("BRIDGE_23RACE_DIR", "") or "").strip()
        self._postfix = str(self.settings.get("BRIDGE_23RACE_POSTFIX", "mita") or "").strip()
        self.bridge_client = BridgeClient(
            cmd_dir=(custom_dir or None),
            postfix=self._postfix or "mita",
        )
        set_bridge_client(self.bridge_client)

    def _load_settings(self):
        self._enabled = bool(self.settings.get("ENABLE_23RACE_BRIDGE", False))
        self._direct_lua_enabled = bool(self.settings.get("ENABLE_23RACE_DIRECT_LUA", False))
        self._programmer_preset_id = self.settings.get("BRIDGE_23RACE_PROGRAMMER_PRESET")

    @property
    def is_enabled(self):
        return self._enabled

    @property
    def is_connected(self):
        return self._enabled and self.bridge_client.is_game_running()

    def _on_setting_changed(self, event: Event):
        data = getattr(event, "data", None) or {}
        key = str(data.get("key") or "")
        if key in ("ENABLE_23RACE_BRIDGE", "ENABLE_23RACE_DIRECT_LUA",
                    "BRIDGE_23RACE_DIR", "BRIDGE_23RACE_PROGRAMMER_PRESET",
                    "BRIDGE_23RACE_POSTFIX"):
            was_enabled = self._enabled
            self._load_settings()
            if key in ("BRIDGE_23RACE_DIR", "BRIDGE_23RACE_POSTFIX"):
                self._init_bridge()
            if not was_enabled and self._enabled:
                self._inject_system_prompt()
                self._sync_tool_settings()
                logger.info("[Race23] Bridge enabled via settings change")
            elif was_enabled and not self._enabled:
                self._sync_tool_settings()
                logger.info("[Race23] Bridge disabled via settings change")
            elif key == "ENABLE_23RACE_DIRECT_LUA":
                self._sync_tool_settings()
                self._inject_system_prompt()
            self.event_bus.emit(Events.GUI.UPDATE_STATUS_COLORS)

    def _sync_tool_settings(self):
        from managers.settings_manager import SettingsManager
        inst = SettingsManager.instance
        if inst is None:
            return
        inst.settings["TOOL_ENABLED_generate_23race_action"] = self._enabled
        inst.settings["TOOL_ENABLED_exec_23race_lua"] = self._enabled and self._direct_lua_enabled
        inst.save_settings()
        logger.info("[Race23] Tool settings synced: generate=%s direct=%s",
                    self._enabled, self._enabled and self._direct_lua_enabled)

    def _inject_system_prompt(self):
        prompt = _read_prompt("Common/23race_bridge.system")
        if not prompt:
            logger.warning("[Race23] System prompt file not found: Common/23race_bridge.system")
            return
        if not self._direct_lua_enabled:
            prompt = self._strip_direct_lua_section(prompt)
        bus = self.event_bus
        bus.emit(Events.Model.ADD_TEMPORARY_SYSTEM_INFO, {"content": prompt})
        bus.emit(Events.Model.ADD_TEMPORARY_SYSTEM_INFO, {"content": prompt})
        logger.info("[Race23] System prompt injected (x2)")

    @staticmethod
    def _strip_direct_lua_section(text: str) -> str:
        import re
        text = re.sub(
            r'<!-- DIRECT_LUA_SECTION_START -->.*?<!-- DIRECT_LUA_SECTION_END -->',
            '',
            text,
            flags=re.DOTALL,
        )
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _on_bridge_reset(self, event: Event):
        try:
            n = self.bridge_client.reset()
            logger.info("[Race23] Bridge reset: cleared %d file(s)", n)
            return True
        except Exception as e:
            logger.error(f"[Race23] Bridge reset failed: {e}")
            return False

    def _on_bridge_status(self, event: Event):
        return {
            "enabled": self._enabled,
            "connected": self.is_connected,
            "cmd_dir": self.bridge_client.cmd_dir,
            "dir_exists": self.bridge_client.is_configured,
        }

    def _on_response_done(self, event: Event):
        if self._enabled:
            self._inject_system_prompt()

    def _on_generate_action(self, event: Event):
        data = getattr(event, "data", None) or {}
        description = str(data.get("description") or "").strip()
        if not description:
            return "[generate_23race_action] Пустое описание."

        MAX_PROGRAMMER_ATTEMPTS = 3
        lua_code = None
        last_error = None

        for attempt in range(MAX_PROGRAMMER_ATTEMPTS):
            try:
                lua_code = self._generate_lua(description, lua_code, last_error)
            except Exception as e:
                logger.error(f"[Race23] Code generation failed (attempt {attempt+1}): {e}", exc_info=True)
                return f"[generate_23race_action] Ошибка генерации кода: {e}"

            if not lua_code:
                return "[generate_23race_action] Нейросеть не сгенерировала код."

            try:
                ok, result = self.bridge_client.exec_lua(lua_code, timeout=30.0)
            except Exception as e:
                return f"[generate_23race_action] Ошибка исполнения: {e}"

            if ok:
                return f"[generate_23race_action] Результат:\n{result}"

            last_error = result
            logger.warning(f"[Race23] Lua error (attempt {attempt+1}/{MAX_PROGRAMMER_ATTEMPTS}): {last_error[:200]}")

        return f"[generate_23race_action] Код после {MAX_PROGRAMMER_ATTEMPTS} попыток:\n---\n{lua_code}\n---\nОшибка в игре: {last_error}"

    def _generate_lua(self, description, previous_code=None, previous_error=None):
        system_prompt = _read_prompt("Common/23race_programmer_prompt.txt")
        if not system_prompt:
            logger.warning("[Race23] Programmer prompt file not found")

        preset_id = self._programmer_preset_id
        if preset_id is None:
            preset_id = self.settings.get("LAST_API_PRESET_ID", 0)

        from managers.api_preset_resolver import ApiPresetResolver
        from managers.provider_manager import ProviderManager
        from handlers.llm_providers.base import LLMRequest

        resolver = ApiPresetResolver(settings=self.settings, event_bus=self.event_bus)

        try:
            preset = resolver.resolve(preset_id)
        except Exception as e:
            raise RuntimeError(f"Failed to resolve programmer preset: {e}")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if previous_code and previous_error:
            messages.append({"role": "user", "content": "This code:\n```lua\n" + previous_code + "\n```\nFailed with error: " + previous_error + "\n\nFix it and return ONLY the corrected ```lua\n...\n``` block."})
        messages.append({"role": "user", "content": description})

        caps = dict(preset.capabilities or {})
        caps.pop("structured_output", None)
        caps.pop("tools_prompt", None)

        req = LLMRequest(
            model=preset.api_model,
            messages=messages,
            api_key=preset.api_key,
            api_url=preset.api_url,
            protocol_id=preset.protocol_id,
            dialect_id=preset.dialect_id,
            provider_name=preset.provider_name,
            headers=dict(preset.headers or {}),
            transforms=list(preset.transforms or []),
            capabilities=caps,
            stream=False,
            tools_on=False,
            settings=self.settings,
        )

        pm = ProviderManager()
        response = pm.generate(req)

        logger.info("[Race23] Programmer raw response (first 500): %s", str(response.text)[:500])

        if response.error_message and not response.text:
            raise RuntimeError(f"Provider error: {response.error_message}")

        text = str(response.text or "")
        return self._extract_lua(text)

    def _extract_lua(self, text):
        import re
        text = str(text or "")
        fence = re.search(r"```lua\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if fence:
            return fence.group(1).strip()
        fence_any = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
        if fence_any:
            code = fence_any.group(1).strip()
            if not code.strip().startswith('{'):
                return code
        stripped = text.strip()
        if stripped.startswith('{') or stripped.startswith('['):
            raise RuntimeError("Programmer returned JSON, not Lua code: " + stripped[:200])
        return stripped
