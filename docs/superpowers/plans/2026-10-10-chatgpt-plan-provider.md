# ChatGPT plan provider implementation plan

**Goal:** Implement the attached architectural audit without replacing shared
HTTP transport or ModelController.

**Architecture:** Declarative provider settings, an application authentication
boundary, and a Responses inference adapter compose the existing provider.

**Spec:** [Provider boundaries](../specs/2026-10-10-chatgpt-plan-provider-design.md)

**Execution:** Inline in the current task, as requested by the user.

## Tasks and evidence

- [x] Create `codex/chatgpt-plan-architecture`; merge the requested source branch.
  Resolve the check-button conflict while preserving local URL validation.
- [x] Add failing regression checks for unsafe destinations, credential headers,
  redirects, lost images/instructions/tool history and GUI coupling. Implement
  the descriptor/service boundary and provider guards.
- [x] Add registration persistence, sign-out/revocation and account selection.
  Verify real DPAPI write/reload. Fix the upstream incorrect tuple indexing of
  `CryptProtectData`; reject unprotected and unreadable credential envelopes.
- [x] Add a failing rotating-token test; serialize mutations with portalocker
  and reload the disk record before refresh.
- [x] Add stream-event and tool-output regression checks; use shared SSE/event
  infrastructure and normalize function calls to the existing application contract.
- [x] Exercise real resolver, runner and provider against mock Responses SSE,
  parsing the result as `StructuredResponse` and checking usage/events.
- [x] Add offscreen Qt checks for protocol-based visibility and account commands.
  Adjust three existing f-string quotations in the touched UI for Python 3.11
  compatibility; no style behavior changes.
- [x] Add a failing settings-schema test; expose supported parameters and migrate
  prior generic settings through protocol metadata.
- [x] Run final focused suite and syntax/diff checks; review all changed files.
- [x] Commit an explicit task-file allowlist; exclude `prompt_editor` and any
  generated changes from test execution. Keep the branch local.

## Verification command

Use `.venv/Scripts/python.exe -m pytest` with `PYTHONPATH=src`,
`QT_QPA_PLATFORM=offscreen`, and `-p no:cacheprovider`. Real DPAPI verification
requires execution outside the restricted sandbox.

Target suites: the three original ChatGPT plan tests, architecture and provider
UI tests, `test_llm_http_transport`, `test_api_settings_check_button`,
`test_preset_model_settings`, `test_endpoint_settings_ui`, and
`test_api_configuration_startup`.

## Review focus

- Custom OAuth protocol with a non-subscription template must route by protocol.
- Switching protocols must restore fields and keep pending action buttons disabled.
- A signed-out registration must reuse its issued client ID on reauthorization.
- A rotated token in a second process must supersede stale in-memory credentials.
- Model tool calls must never execute an unadvertised tool or bypass ModelController.

Independent reviewer tools were unavailable; review is performed in this task.

Final focused verification: 105 tests and 17 subtests passed in 11.90 seconds.
Python compilation and `git diff --check` passed. General-suite and live-service
limitations are recorded in the specification.
