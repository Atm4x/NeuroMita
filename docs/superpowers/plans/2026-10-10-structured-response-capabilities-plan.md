# Structured Response Capabilities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send only request-usable structured fields while keeping schema, prompt, and execution policy aligned.

**Architecture:** Add an immutable profile resolver in `services` that combines existing runtime policy with request facts. Feed it through prompt construction and provider capabilities, use shared schema options for every provider, and sanitize disallowed control fields before execution.

**Tech Stack:** Python 3.12, Pydantic, application DSL, unittest/pytest test modules.

**Spec:** [2026-10-10-structured-response-capabilities-design.md](../specs/2026-10-10-structured-response-capabilities-design.md)

## Global Constraints

- Preserve the full internal Pydantic `StructuredResponse` and persisted response compatibility.
- Do not persist request-only capability metadata in character variables.
- Do not add or alter providers; Responses is not part of this branch unless already on `releases`.
- Keep Unity changes out of scope and preserve current Unity intent contracts.
- Do not issue paid provider calls.

## Review Focus

- Profile state survives retry, fallback, and tool continuation without being recomputed from a different context.
- Strict OpenAI-compatible schemas keep required nullable semantics after exclusions.
- Non-strict provider output cannot execute unavailable operations.
- Empty/default statistics and independent character memory remain intact.
- Prompt DSL renders field guidance and examples matching each profile.

---

### Task 1: Profile resolver and its behavior tests

**Files:**
- Create: `src/services/structured_response_capabilities.py`
- Modify: `src/services/contracts.py` only if an established service contract is needed
- Test: `src/utils/Testing/test_structured_response_capabilities.py`

- [x] Add tests for graph, tools/mode/depth, reminders/timers, secret mechanics, images, runtime Unity/program fields, and custom/intents overlays.
- [x] Run the focused tests and confirm they fail for missing profile behavior.
- [x] Implement immutable profile resolution and profile finalization from prompt rendering.
- [x] Run the focused tests.

### Task 2: Request-local prompt and execution integration

**Files:**
- Modify: `src/controllers/model_controller.py`
- Modify: `src/controllers/prompt_controller.py`
- Modify: `src/services/contracts.py`
- Modify: `extra/Prompts/Structural/response_format_json.script`
- Test: focused tests under `src/utils/Testing/`

- [x] Test sanitized execution fields and request-local prompt feature overrides without character-variable writes.
- [x] Implement profile propagation, prompt feature exposure, and response sanitization before character handlers.
- [x] Ensure retry, fallback, and tool continuation use the same profile snapshot.
- [x] Render representative real DSL branches and verify schema instructions/examples reflect them.

### Task 3: Provider schema integration and regression verification

**Files:**
- Modify: `src/handlers/llm_providers/openai_http_base.py`
- Modify: `src/handlers/llm_providers/openai_compatible.py`
- Modify: `src/handlers/llm_providers/gemini_provider.py`
- Modify: `src/schemas/structured_response.py` only if a shared schema-options helper belongs there
- Tests: structured schema/provider tests under `src/utils/Testing/`

- [x] Add strict-schema tests for property removal, nullable required secret, and full-model defaults.
- [x] Use one shared mapping from profile to schema exclusions/requirements in all existing providers.
- [x] Run focused structured-response tests and the release prompt contracts.
- [x] Run the known MVVM baseline test and report its status separately.
- [x] Review diff scope, commit, push branch, and create a PR targeting `releases`; do not merge.

## Execution

Execute tasks in order in the existing isolated worktree. Use the focused suite plus the specific baseline check; do not run unrelated test suites unless a focused regression requires them.
