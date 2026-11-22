from __future__ import annotations

from dataclasses import dataclass
from typing import ContextManager, Protocol

from .models import JsonDocument


class SnapshotParticipant(Protocol):
    key: str
    version: int

    def paused(self) -> ContextManager[None]: ...

    def capture(self) -> JsonDocument: ...

    def validate(self, state: JsonDocument) -> None: ...

    def apply(self, state: JsonDocument, *, branch_id: str) -> None:
        """Restore owned state and rebuild disposable views for the explicit branch world."""


@dataclass(frozen=True, slots=True)
class PendingRestore:
    operation_id: str
    workspace: str
    source_branch_id: str
    target_branch_id: str
    before: JsonDocument
    desired: JsonDocument


class RestorationJournal(Protocol):
    """Durable recovery authority for one in-progress transition per workspace."""

    def pending(self, workspace: str) -> PendingRestore | None:
        """Resolve uncertain admission/completion from committed storage state."""

    def begin(self, operation: PendingRestore) -> None:
        """Retain both worlds before participant mutation; exact retries are idempotent."""

    def complete(self, operation_id: str) -> None:
        """Remove finished recovery authority idempotently after apply/compensation and resume."""
