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
- Final selected regression suite: 448 tests and 20 subtests passed. Includes
  mocked HTTP/SSE, both Completions transports, Responses, sparse schema/profile
  parity, native execution, SQLite history reload/projection, cancellation,
  retries/fallback and SIWC endpoint/redirect/header protections. Windows DPAPI
  tests passed outside the sandbox; sandbox CryptProtectData failed independently
  of the changes.
- Six mock end-to-end paths use ChatModel -> request runner -> ProviderManager ->
  real httpx MockTransport -> normalized calls -> existing runtime executor ->
  follow-up: Responses, HTTP Completions and SDK Completions, streaming on/off.
- Live gemini-3.5-flash-lite, using the user-selected Google account and Google's
  OpenAI-compatible endpoint: HTTP/nonstream and SDK/stream text returned OK;
  both tool/follow-up paths ran calculator once and returned 2. Ordinary and
  sparse structured output returned OK and passed the runtime parser without
  response-format fallback. Google thought signatures survive tool history.
- Responses and SIWC live acceptance remain unverified: the supplied Google
  endpoint's documented compatibility covers Chat Completions. Neither OAuth
  credentials nor saved user presets were changed for live checks.
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
