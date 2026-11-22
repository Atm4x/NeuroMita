from __future__ import annotations

from typing import Protocol, Sequence

from .models import AppendReceipt, Branch, EventDraft, JsonDocument, TimelineEvent, TimelineSelection
from .archive import SessionArchive


class TimelineRepository(Protocol):
    """Storage laws shared by SQLite and future CFMD implementations.

    A branch world includes its local events and inherited prefixes, clipped at
    every ancestral fork. Sequence is application ordering, not a database
    revision. Each read must return a coherent committed world. Event values are
    immutable and detached from storage; derived caches carry no authority.
    """

    def create_session(self, session_id: str, branch_id: str) -> Branch:
        """Atomically create an empty root; identical identity pairs are retries."""

    def get_branch(self, branch_id: str) -> Branch:
        """Return explicit branch metadata independently of workspace selection."""

    def list_branches(self) -> tuple[Branch, ...]:
        """Return retained session and branch identities without loading event payloads."""

    def append(
        self, branch_id: str, events: Sequence[EventDraft], *,
        expected_head: int, idempotency_key: str,
        command: JsonDocument | None = None,
    ) -> tuple[TimelineEvent, ...]:
        """Commit events, head and receipt together, or change nothing.

        Validate causality and knowledge against the preceding world, including
        earlier events in this batch. A matching receipt returns its original
        events even when expected_head is stale. A reused key with different
        semantic intent conflicts; a fresh key requires the exact current head.
        Empty batches may retain command receipts without advancing the head.
        Attachment references must resolve before publication.
        """

    def receipt(self, branch_id: str, key: str) -> AppendReceipt | None:
        """Return committed command intent and its original ordered event values."""

    def read(
        self, branch_id: str, *, after: int = 0, through: int | None = None,
        limit: int = 500, observer: str | None = None,
    ) -> tuple[TimelineEvent, ...]:
        """Read ascending positions with after < sequence <= through/current head.

        Observer filtering selects direct witnesses of each event. Expanding
        disclosures and applying context resets belong to the knowledge fold;
        this primitive must not silently perform either projection.
        """

    def get_event(self, branch_id: str, event_id: str) -> TimelineEvent:
        """Resolve only within this branch world, including hidden retained facts."""

    def find_message(self, branch_id: str, message_id: str) -> TimelineEvent:
        """Resolve a unique external message identity within this branch world."""

    def knows(self, branch_id: str, character_id: str, event_id: str, *, through: int | None = None) -> bool:
        """Apply witnessing/disclosure since the latest direct character reset.

        Hidden messages remain known facts. Unknown and excluded-future event
        identities return False rather than granting knowledge by adjacency.
        """

    def context_epoch(self, branch_id: str, character_id: str, *, through: int | None = None) -> int:
        """Return the latest direct character-reset sequence, or zero."""

    def presentation_epoch(self, branch_id: str, character_id: str, *, through: int | None = None) -> int:
        """Return the latest direct reset/hide/revise/restore sequence, or zero."""

    def present(self, branch_id: str, *, through: int | None = None) -> frozenset[str]:
        """Fold explicit joins/leaves independently of conversation knowledge."""

    def fork(self, branch_id: str, checkpoint_id: str, new_branch_id: str) -> Branch:
        """Create child metadata and its marker atomically at a retained checkpoint.

        Reusing the same child identity and source checkpoint is an exact retry.
        Parent futures remain retained and excluded from the child's world.
        """

    def export_session(self, session_id: str) -> SessionArchive:
        """Capture all branches, receipts and reachable assets in one coherent view."""

    def import_session(self, archive: SessionArchive) -> Branch:
        """Validate and import the complete archive atomically, preserving identities.

        Collisions reject the import; existing sessions and active workspace
        selections are never overwritten by a transfer.
        """


class TimelineWorkspace(Protocol):
    def selection(self, workspace: str) -> TimelineSelection | None:
        """Read the durable branch selection and its generation, or no selection."""

    def select(
        self, workspace: str, branch_id: str, *, expected: TimelineSelection | None,
    ) -> TimelineSelection:
        """Compare-and-set a retained branch; every success advances generation.

        Selecting the same branch again still invalidates earlier captures.
        None matches only a previously uninitialized workspace.
        """
