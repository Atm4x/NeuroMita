from managers.tools.base import Tool
from game_connections.race23 import get_bridge_client


class Exec23RaceLuaTool(Tool):
    name = "exec_23race_lua"
    description = (
        "Исполняет Lua-код напрямую в карте Warcraft III «23 Race Legion». "
        "Для чтения: return AiRace[1]. Для модификации: пиши код."
    )

    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Lua-код для исполнения в карте. Для чтения начни с return."
            }
        },
        "required": ["code"]
    }

    def run(self, code: str, **_) -> str:
        from managers.settings_manager import SettingsManager
        if not SettingsManager.get("ENABLE_23RACE_DIRECT_LUA", False):
            return "[exec_23race_lua] Прямое исполнение Lua отключено. Используй generate_23race_action с описанием на русском."
        bridge = get_bridge_client()
        if bridge is None:
            return "[exec_23race_lua] Мост 23 Race не инициализирован. Включи его в настройках Игры."
        if not bridge.is_configured:
            return "[exec_23race_lua] Папка CustomMapData не найдена. Убедись, что Warcraft III запущен."
        try:
            ok, result = bridge.exec_lua(code)
        except Exception as e:
            return f"[exec_23race_lua] Ошибка исполнения: {e}"
        if not ok:
            return f"[exec_23race_lua] Ошибка в игре: {result}"
        return f"[exec_23race_lua] Результат:\n{result}"
