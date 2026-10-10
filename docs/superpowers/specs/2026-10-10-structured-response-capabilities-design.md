# Request-scoped structured response capabilities

## Goal and constraints

Build one request-scoped description of which structured response fields the application can use. Derive provider schema exclusions, prompt guidance, and post-parse execution permissions from that description. Keep the full Pydantic response model and saved response shape compatible. Provider support for constrained output remains separate from application capability.

The profile must snapshot settings, selected preset/mode, runtime connection, character mechanics, actual tools, prompt-declared intents, and images available in the assembled context. It must travel unchanged through provider retries, preset fallback, and tool continuation. Request-only state must not be written into character variables.

## Ownership and behavior

- `RuntimeCapabilitiesService` remains the owner of Unity connection and Unity-only segment fields. Program fields (`commands`, `music`, `start_game`, `end_game`) remain available without Unity.
- A dedicated structured-capabilities service combines that runtime snapshot with existing settings and request facts. `ModelController` supplies facts already gathered for the request; it does not grow new field-specific policy.
- Graph fields are available only when both `RAG_ENABLED` and `GRAPH_EXTRACTION_ENABLED` are true. Structured graph storage does not require `GRAPH_EXTRACTION_INLINE`; that setting governs the legacy inline-tag path.
- `tool_call` is available only with usable configured tools, enabled tool prompt/mode, structured output, and remaining tool depth. Execution still checks tool name and depth for non-strict providers.
- `reminder_add` and `reminder_delete` follow reminder availability; `timer_add` is evaluated separately even though the current scheduler's `REMINDERS_ENABLED` gate controls both.
- `image_description` is available when image content is present anywhere in the assembled provider context, including retained history.
- `secret_exposed` is only sent for characters using the secret mechanic while it is unresolved. It remains required and nullable then. Stats and memory fields are not removed based on empty values or disabled RAG.
- Existing dynamic custom fields, working state, reasoning, Unity runtime exclusions, and DSL `support_intents` remain owned by their current sources and feed this profile.

## Data flow

Resolve the base profile after preset, settings, enabled tools, and character are known. Pass it through `PromptBuildRequest` as request data, not persisted character state. Prompt DSL receives request-local feature overrides from the profile and continues to own `support_intents`. Finalize the profile with the rendered prompt result, expose common schema options to providers through `LLMRequest.capabilities`, and sanitize parsed control fields before calling character handlers. The immutable profile and the same provider capability mapping follow retries, fallback, and tool continuation.

The canonical Pydantic model remains permissive and complete. Schema builders remove unavailable properties and update `required` consistently; strict schema modes stay strict. Provider adapters only translate the shared schema options into their wire format. JSON/prompt-only modes receive the same field availability guidance and execution checks.

## Validation

Cover remote-only and Unity-linked fields; graph settings and inline mode; tools disabled/enabled, native/schema modes and depth; reminder and timer fields; secret and non-secret characters; working state, custom fields and intents; images in current and historical context; retry/fallback/tool continuation; minimum response parsing and unchanged memory/stat defaults. Render the actual shared prompt DSL branches. Run focused structured-response tests and the known MVVM baseline test separately, reporting any pre-existing failure distinctly. No paid provider calls.
