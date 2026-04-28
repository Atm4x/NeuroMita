from __future__ import annotations

from main_logger import logger

from .block_base import ControllerBlock
from .block_context import BlockContext


class RAGBlock(ControllerBlock):
    name = "rag"
    enabled_setting = "BLOCK_RAG_ENABLED"
    default_enabled = False
    dependencies = ("ai_engine",)

    def initialize(self, ctx: BlockContext) -> None:
        from controllers.embedding_controller import EmbeddingController
        from controllers.embedding_presets_controller import EmbeddingPresetsController
        from controllers.graph_controller import GraphController

        embedding_presets = EmbeddingPresetsController()
        self.controllers["embedding_presets_controller"] = embedding_presets
        logger.notify("EmbeddingPresetsController успешно инициализирован.")

        embedding = EmbeddingController()
        self.controllers["embedding_controller"] = embedding
        logger.notify("EmbeddingController успешно инициализирован.")

        graph = GraphController()
        self.controllers["graph_controller"] = graph
        logger.notify("GraphController успешно инициализирован.")
