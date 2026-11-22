from __future__ import annotations

from time import monotonic
from uuid import uuid4

from domain.timeline import JsonDocument


class GameSnapshotEndpoint:
    """GUI-thread RPC for exact, paused game state; responses use a dedicated queue."""

    def __init__(self, responses, notifications, capture, apply, pause, state_queue=None):
        self.responses = responses
        self.notifications = notifications
        self.capture = capture
        self.apply = apply
        self.pause = pause
        self.paused = False
        self.state_queue = state_queue

    def handle(self, command) -> bool:
        action = command.get("action", "")
        if action not in {"session_pause", "session_restore", "session_resume"}:
            return False
        identity = command.get("request_id")
        try:
            if action == "session_pause":
                self.pause(True)
                self.paused = True
                state = JsonDocument(self.capture()).to_dict()
                if self.notifications is not None:
                    self.notifications.put({"event": "session_barrier", "request_id": identity})
            elif action == "session_restore":
                if not self.paused:
                    raise RuntimeError("A game must be paused before restoring its state")
                if self.state_queue is not None:
                    self.state_queue.generation += 1
                self.apply(command["state"])
                state = JsonDocument(self.capture()).to_dict()
            else:
                self.pause(False)
                self.paused = False
                state = None
            response = {"request_id": identity, "state": state,
                        "generation": self.state_queue.generation if self.state_queue is not None else 0}
        except Exception as exc:
            response = {"request_id": identity, "error": str(exc)}
        if self.responses is not None:
            self.responses.put(response)
        return True


def snapshot_request(commands, responses, action, *, state=None, timeout=15, details=False):
    if commands is None or responses is None:
        raise RuntimeError("This game process does not expose session snapshot RPC")
    identity = uuid4().hex
    commands.put({"action": action, "request_id": identity, "state": state})
    deadline = monotonic() + timeout
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError("Game snapshot acknowledgement timed out")
        response = responses.get(timeout=remaining)
        if response.get("request_id") != identity:
            continue
        if "error" in response:
            raise RuntimeError(response["error"])
        return identity, response if details else response.get("state")


class GameStateQueue:
    """Tag views with the process restore generation so queued old boards stay stale."""

    def __init__(self, queue):
        self.queue = queue
        self.generation = 0

    def put(self, state):
        self.queue.put(dict(state, _session_generation=self.generation))


def validate_game_state(game_id, state):
    JsonDocument(state)
    if game_id == "chess":
        from modules.Chess.board_logic import PureBoardLogic
        board = PureBoardLogic()
        board.restore_snapshot(state["board"])
        if (set(state) != {"board", "elo", "player_is_white", "is_auto", "is_cheat", "react_enabled", "engine_pending"}
                or type(state["elo"]) is not int or not 100 <= state["elo"] <= 4000
                or any(type(state[field]) is not bool for field in ("player_is_white", "is_auto", "is_cheat", "react_enabled", "engine_pending"))):
            raise ValueError("Invalid chess snapshot")
    elif game_id == "seabattle":
        from modules.SeaBattle.seabattle_logic import SeaBattleEngine
        board = SeaBattleEngine()
        board.restore_snapshot(state["board"])
        if set(state) != {"board", "react_enabled"} or type(state["react_enabled"]) is not bool:
            raise ValueError("Invalid Sea Battle snapshot")
    else:
        raise ValueError("Unsupported snapshot game")
