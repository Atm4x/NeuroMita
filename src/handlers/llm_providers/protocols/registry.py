from .contract import ProtocolAdapter


def adapter_for(dialect_id: str) -> ProtocolAdapter:
    if dialect_id == "openai_chat_completions":
        from .chat_completions.adapter import ChatCompletionsAdapter

        return ChatCompletionsAdapter()
    if dialect_id == "openai_responses":
        from .responses.adapter import ResponsesAdapter

        return ResponsesAdapter()
    raise ValueError(f"Unsupported wire dialect: {dialect_id}")
