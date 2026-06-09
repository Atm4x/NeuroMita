from managers.tools.base import Tool
from game_connections.race23 import get_bridge_client
from core.events import get_event_bus, Events


class Generate23RaceActionTool(Tool):
    name = "generate_23race_action"
    description = (
        "ВЫЗОВИ ЭТО КОГДА ИГРОК ПРОСИТ ДЕЙСТВИЕ В ИГРЕ. "
        "Генерирует и исполняет Lua-код в карте Warcraft III «23 Race Legion». "
        "Опиши что сделать на русском. Примеры: 'Дай игроку 1 золото', 'Покажи расы', 'Заспавни юнитов'."
    )

    parameters = {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Описание действия в 23 Race на естественном языке"
            }
        },
        "required": ["description"]
    }

    def run(self, description: str, **_) -> str:
        bridge = get_bridge_client()
        if bridge is None:
            return "[generate_23race_action] Мост 23 Race не инициализирован. Включи его в настройках Игры."
        if not bridge.is_configured:
            return "[generate_23race_action] Папка CustomMapData не найдена. Убедись, что Warcraft III запущен."

        bus = get_event_bus()
        try:
            results = bus.emit_and_wait(Events.Race23.GENERATE_ACTION, {
                "description": description,
            }, timeout=45.0)
            if results and results[0]:
                return str(results[0])
            return "[generate_23race_action] Не удалось сгенерировать или выполнить код."
        except Exception as e:
            return f"[generate_23race_action] Ошибка: {e}"
