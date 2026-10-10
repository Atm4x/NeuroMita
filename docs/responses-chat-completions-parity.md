# Responses and Chat Completions protocol parity

Implementation scope: the architectural proposal supplied on 2026-10-10.

Both wire dialects use the existing request runner, provider manager, HTTP
transport, cancellation and stream channel. Protocol adapters encode requests,
decode responses and consume typed wire events. Credentials and endpoint trust
remain provider responsibilities. Each dialect has its own request/response/stream
modules rather than a second execution pipeline.

Execution plan:

1. Record current tests and add normalized ToolCall/ToolResult response contract.
2. Extract shared Chat Completions semantics for HTTP and SDK transports.
3. Extract Responses codecs and SSE handling, retaining the legacy SIWC interface.
4. Register API-key Responses independently and expose a separate settings profile.
5. Connect native declarations and normalized calls to the existing tool executor,
   preserve call IDs and results in follow-up history, enforce one call per turn.
6. Run mock HTTP, protocol, runner, tool, preset and security regressions, then
   review the integrated changes. Record live verification separately.

Native tool declarations and schema-level tool requests have one request-scoped
policy. Wire adapters return normalized calls; runtime orchestration validates
and bridges them to the existing StructuredResponse executor. A valid tool-only
response succeeds. Multiple calls and malformed or unadvertised calls fail visibly.

Generic Responses supports JSON and SSE independently of UI delta emission.
SIWC retains forced SSE, namespace policy, the exact OpenAI endpoint, blocked
redirects and protected credential headers. No OAuth dependency enters the generic
API-key provider. Existing protocol and template IDs remain valid.

Verification on 2026-10-10:

- Initial baseline: 44 existing Responses/SIWC and HTTP transport tests passed.
- Offline CI regression suite: 343 tests and 3 subtests passed in a clean
  temporary virtual environment on Windows, including SIWC DPAPI coverage. A
  separate regression batch passed 101 tests; its two unrelated failures were
  reproduced against HEAD (hidden game-master result expected an empty string
  but received a single space, and the pre-existing history-reset fixture noted
  below).
- CI regression scope includes mocked HTTP/SSE, both Completions transports, Responses, sparse schema/profile
  parity, native execution, SQLite history reload/projection, cancellation,
  retries/fallback and SIWC endpoint/redirect/header protections. Windows DPAPI
  tests passed outside the sandbox; sandbox CryptProtectData failed independently
  of the changes.
- Ten mock end-to-end paths use ChatModel -> request runner -> ProviderManager ->
  real httpx MockTransport -> normalized calls -> existing runtime executor ->
  follow-up: Responses, HTTP Completions, SDK Completions, Responses-to-Chat HTTP
  fallback and Responses-to-Chat SDK fallback, with UI streaming on and off. The
  two fallback transports also reload the native tool exchange from SQLite and
  project it into the subsequent Chat request.
- Live gemini-3.5-flash-lite, using the user-selected Google account and Google's
  OpenAI-compatible endpoint: HTTP/nonstream and SDK/stream text returned OK;
  both tool/follow-up paths ran calculator once and returned 2. Ordinary and
  sparse structured output returned OK and passed the runtime parser without
  response-format fallback. Google thought signatures survive tool history.
- Live SIWC acceptance with the existing signed-in account and gpt-6-luna: text
  returned OK and a synthetic red-square image returned Red, with UI streaming
  enabled and disabled. A real calculator tool call ran exactly once and its
  follow-up returned 2 in both modes. Strict and sparse structured live requests
  were not run; automatic approval review rejected the additional runtime schema
  payload as outside the authorized live-test scope.
- Live API-key Responses remains unverified; Google gemini-3.5-flash-lite is only
  the Chat Completions endpoint used in the earlier acceptance. No API-key
  Responses preset was supplied. Neither OAuth credentials nor saved user presets
  were changed for these SIWC checks.
- Cross-recovery exactly-once is not guaranteed. Current call_id validation
  prevents replay inside one request, but no durable operation ledger or recovery
  protocol exists for an external side effect completed just before an app crash.
  This is outside current per-turn execution scope.
- Cross-protocol history safety fix: the shared Chat Completions encoder now
  strips Responses-only reasoning/output fields (plus local timestamps) from both
  HTTP and SDK payload builders while preserving native tool calls and provider
  extensions. Regression tests cover Responses-to-Chat fallback and restored
  SQLite tool history for both transports.
- A broader history test run found an existing failure in
  test_history_epoch_guard.HistoryResetHookTests: its __new__ fixture lacks
  _action_memory_cap_warnings, which on_history_reset already accesses at HEAD.
  That unrelated fixture is outside this change. Unrestricted pytest collection
  also traverses bundled libraries and temporary project copies; the passing
  suite uses explicit project test paths.

Protocol references:
[OpenAI Responses migration](https://developers.openai.com/api/docs/guides/migrate-to-responses),
[function calling](https://developers.openai.com/api/docs/guides/function-calling),
[Google OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai).
