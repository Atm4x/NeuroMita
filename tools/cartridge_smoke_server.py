"""Local Unity protocol smoke test. Uses deterministic replies, never calls an LLM."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


async def main():
    from core.events import Events
    from core.request_policy import RequestPolicy
    from core.services import services
    from game_connections.server import ChatServerNew
    from managers.character_manager import CharacterManager
    from managers.character_resource_manager import CharacterResourceManager
    from managers.task_manager import TaskManager, TaskStatus
    from services.cartridge_prompt import build_cartridge_prompt
    from services.character_registry import ManagedCharacterRegistry
    from services.contracts import CharacterRegistry, GameLinkService, PromptBuildRequest, SettingsService, TaskService

    settings = MagicMock(spec=SettingsService)
    settings.get.side_effect = lambda key, default=None: default
    services().register(SettingsService, settings, replace=True)
    manager = object.__new__(CharacterManager)
    manager._lock = threading.RLock()
    manager._definitions = {}
    manager.characters = {}
    manager.current_character = None
    manager.resources = CharacterResourceManager()
    registry = ManagedCharacterRegistry(manager)
    services().register(CharacterRegistry, registry, replace=True)
    tasks = TaskManager()
    task_service = MagicMock(spec=TaskService)
    task_service.create_task.side_effect = tasks.create_task
    task_service.get_task.side_effect = tasks.get_task
    services().register(TaskService, task_service, replace=True)
    services().register(GameLinkService, MagicMock(spec=GameLinkService), replace=True)
    server = ChatServerNew(port=12345)
    server.set_settings_provider(lambda: {})

    class SmokeBus:
        def emit(self, name, data):
            if name != Events.Chat.SEND_MESSAGE:
                return
            asyncio.create_task(self.reply(data))

        async def reply(self, data):
            char_id = data["character_id"]
            character = registry.get(char_id)
            if character is not None:
                prompt = build_cartridge_prompt(PromptBuildRequest(character=character,
                    event_type="chat", policy=RequestPolicy.from_dict(data["policy"]),
                    user_input=data["user_input"], participants=data.get("participants", [])))
                assert not prompt.support_intents
                assert data["policy"]["allow_voiceover"] is False
                text = f"SMOKE {char_id}: связь с картриджем работает."
                character.save_character_state_to_history(prompt.history_messages + [{"role": "assistant", "content": text}])
                print(f"SMOKE_REQUEST character={char_id} history={len(prompt.history_messages)} voice=false", flush=True)
            else:
                text = f"SMOKE {char_id}: обычный участник диалога."
            task = tasks.update_task_status(data["task_uid"], TaskStatus.SUCCESS,
                result={"response": text, "segments": [{"text": text}], "response_protocol_version": 3})
            await server.send_task_update(task.data["client_id"], task)

    server.event_bus = SmokeBus()
    print("CARTRIDGE_SMOKE_SERVER localhost:12345; deterministic provider; temporary history", flush=True)
    await asyncio.wait_for(server.start_async(), timeout=900)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="neuromita-cartridges-") as directory:
        os.environ["NEUROMITA_HISTORIES_DIR"] = directory
        try:
            asyncio.run(main())
        except (KeyboardInterrupt, TimeoutError):
            pass
