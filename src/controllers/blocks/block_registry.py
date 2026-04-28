from __future__ import annotations

from typing import Dict, List, Optional

from main_logger import logger

from .block_base import ControllerBlock
from .block_context import BlockContext


class BlockRegistry:
    """Holds blocks, initializes them in dependency order, shuts down in reverse."""

    def __init__(self) -> None:
        self._blocks: Dict[str, ControllerBlock] = {}
        self._init_order: List[str] = []

    def register(self, block: ControllerBlock) -> None:
        if not block.name:
            raise ValueError(f"Block {type(block).__name__} has empty name")
        if block.name in self._blocks:
            raise ValueError(f"Block '{block.name}' already registered")
        self._blocks[block.name] = block

    def get(self, name: str) -> Optional[ControllerBlock]:
        return self._blocks.get(name)

    def is_active(self, name: str) -> bool:
        blk = self._blocks.get(name)
        return bool(blk and blk.active)

    def initialize(self, ctx: BlockContext) -> None:
        order = self._toposort()
        for name in order:
            block = self._blocks[name]
            if not block.is_enabled(ctx):
                logger.info(f"[BlockRegistry] Block '{name}' disabled — skipping")
                continue
            missing_dep = next(
                (d for d in block.dependencies if not self.is_active(d)),
                None,
            )
            if missing_dep:
                logger.info(
                    f"[BlockRegistry] Block '{name}' skipped: dependency '{missing_dep}' not active"
                )
                continue
            try:
                block.initialize(ctx)
                block.active = True
                ctx.blocks[name] = block
                self._init_order.append(name)
                logger.success(f"[BlockRegistry] Block '{name}' initialized")
            except Exception as e:
                logger.error(f"[BlockRegistry] Block '{name}' init failed: {e}", exc_info=True)

    def shutdown(self) -> None:
        for name in reversed(self._init_order):
            block = self._blocks.get(name)
            if not block:
                continue
            try:
                block.shutdown()
                block.active = False
            except Exception as e:
                logger.error(f"[BlockRegistry] Block '{name}' shutdown failed: {e}", exc_info=True)

    def _toposort(self) -> List[str]:
        visited: Dict[str, int] = {}
        order: List[str] = []

        def visit(name: str, stack: List[str]) -> None:
            state = visited.get(name, 0)
            if state == 1:
                return
            if state == 2:
                cycle = " -> ".join(stack + [name])
                raise ValueError(f"Block dependency cycle: {cycle}")
            visited[name] = 2
            block = self._blocks.get(name)
            if block:
                for dep in block.dependencies:
                    if dep in self._blocks:
                        visit(dep, stack + [name])
                    else:
                        logger.warning(
                            f"[BlockRegistry] Block '{name}' depends on unknown '{dep}'"
                        )
            visited[name] = 1
            order.append(name)

        for n in self._blocks:
            visit(n, [])
        return order
