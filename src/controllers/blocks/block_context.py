from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class BlockContext:
    """Shared state passed to every block during initialize().

    `settings` is the live SettingsManager-backed dict (from MainController).
    `event_bus` is the shared EventBus.
    `view` is optional PyQt main window (None in headless mode).
    `cli_args` is parsed argparse Namespace (or None).
    `main_controller` is the back-reference for legacy controllers that still
    need it; new code should rely on settings + event_bus only.
    `blocks` is filled by the registry as blocks initialize, so later blocks
    may inspect already-initialized ones.
    """

    settings: Any
    event_bus: Any
    view: Any = None
    cli_args: Any = None
    main_controller: Any = None
    blocks: Dict[str, Any] = field(default_factory=dict)

    def get_block(self, name: str) -> Optional[Any]:
        return self.blocks.get(name)
