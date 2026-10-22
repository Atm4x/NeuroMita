from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from threading import RLock
from typing import Iterator

from domain.timeline import ConcurrentTimelineWrite, JsonDocument, new_id
from domain.timeline.models import TimelineSelection, TimelineTurn, TurnKind
from domain.timeline.ports import TimelineRepository, TimelineWorkspace
from core.cancellation import CancellationToken
from .session_timeline import SessionTimeline


class SessionTimelineRuntime:
    """Application owner of the durable selection and generation-local worlds."""

    def __init__(
        self, repository: TimelineRepository, workspace: TimelineWorkspace, *,
        workspace_name: str = "desktop",
    ):
        self.repository = repository
        self.workspace = workspace
        self.workspace_name = workspace_name
        self._lock = RLock()
        self._cancellations = {}
        self._turn: ContextVar[TimelineTurn | None] = ContextVar("session_timeline_turn", default=None)
        if workspace.selection(workspace_name) is None:
            initial = SessionTimeline.create(repository)
            try:
                workspace.select(workspace_name, initial.branch_id, expected=None)
            except ConcurrentTimelineWrite:
                if workspace.selection(workspace_name) is None:
                    raise

    @property
    def selection(self) -> TimelineSelection:
        selected = self.workspace.selection(self.workspace_name)
        if selected is None:
            raise RuntimeError("Session timeline workspace has no active branch")
        return selected

    @property
    def timeline(self) -> SessionTimeline:
        turn = self._turn.get()
        branch_id = turn.selection.branch_id if turn else self.selection.branch_id
        return SessionTimeline(self.repository, branch_id)

    @property
    def turn(self) -> TimelineTurn | None:
        return self._turn.get()

    def capture(
        self, *, trigger_id: str | None = None, kind: TurnKind = TurnKind.INITIATE,
        character_id: str = "", include_target: bool = False,
        input_event_ids: tuple[str, ...] = (),
    ) -> TimelineTurn:
        with self._lock:
            selection = self.selection
            timeline = SessionTimeline(self.repository, selection.branch_id)
            head = timeline.branch.head_sequence
            epoch = (self.repository.context_epoch(selection.branch_id, character_id, through=head)
                     if character_id else 0)
            return TimelineTurn(selection, head, trigger_id, kind, character_id, epoch, include_target, input_event_ids)

    @contextmanager
    def turn_scope(self, turn: TimelineTurn, *, cancellation: CancellationToken | None = None) -> Iterator[SessionTimeline]:
        token = self._turn.set(turn)
        registration = object()
        try:
            with self._lock:
                self.assert_current()
                if cancellation is not None:
                    cancellation.raise_if_cancelled()
                    self._cancellations[registration] = (cancellation, turn)
            yield self.timeline
        finally:
            if cancellation is not None:
                with self._lock:
                    self._cancellations.pop(registration, None)
            self._turn.reset(token)

    def assert_current(self) -> None:
        turn = self._turn.get()
        if turn is not None and turn.selection != self.selection:
            raise ConcurrentTimelineWrite("The active session changed while the turn was running")
        if turn and turn.character_id:
            epoch = self.repository.context_epoch(turn.selection.branch_id, turn.character_id)
            if epoch != turn.context_epoch:
                raise ConcurrentTimelineWrite("The character context changed while the turn was queued or running")
        if turn and turn.trigger_id and turn.character_id:
            if not self.timeline.knows(turn.character_id, turn.trigger_id):
                raise ConcurrentTimelineWrite("The character context was reset while the turn was running")

    @contextmanager
    def writing(self) -> Iterator[SessionTimeline]:
        with self._lock:
            self.assert_current()
            yield self.timeline

    def activate(self, branch_id: str) -> TimelineSelection:
        with self._lock:
            current = self.selection
            selection = self.workspace.select(self.workspace_name, branch_id, expected=current)
            cancellations = tuple(cancellation for cancellation, _turn in self._cancellations.values())
        for cancellation in cancellations:
            cancellation.cancel("Session timeline changed")
        return selection

    def cancel_character(self, character_id: str) -> None:
        with self._lock:
            tokens = tuple(token for token, turn in self._cancellations.values()
                           if turn.character_id == character_id)
        for token in tokens:
            token.cancel("Character timeline context was reset")

    def start_session(self) -> SessionTimeline:
        timeline = SessionTimeline.create(self.repository)
        self.activate(timeline.branch_id)
        return timeline

    def restore(self, checkpoint_id: str, *, branch_id: str | None = None) -> JsonDocument:
        with self._lock:
            restored = self.timeline.fork(checkpoint_id, branch_id=branch_id or new_id())
        self.activate(restored.timeline.branch_id)
        return restored.snapshot
