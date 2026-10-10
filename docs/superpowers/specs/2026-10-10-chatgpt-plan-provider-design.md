# ChatGPT plan provider boundaries

Implements the user's attached audit of NeuroMitaPython branch
`codex/chatgpt-plan-provider` at `ad7fedc0`. The local feature branch starts
from `dorabotki-total-09.10.2026` and merges that implementation, preserving
the newer endpoint editor and unrelated changes in `prompt_editor`.

## Contracts

- `ProviderDescriptor` describes account actions and settings visibility.
  GUI code renders this contract instead of identifying template 12 or
  importing OAuth implementations.
- `AuthenticationService` supplies sign-in, account selection, sign-out,
  account state and model listing. `services/provider_settings.py` is its
  application composition boundary. Account operations run in the existing
  API controller's supervised worker and return existing result events.
- `ResponsesInferenceAdapter` translates messages, supported parameters
  and tool output. ModelController, request retries and fallback routing
  continue to use their existing contracts.

## Security and account lifecycle

Inference accepts only `https://api.openai.com/v1/responses`, validates that
destination before loading credentials, protects authorization and routing
headers, and disables redirects per request through the shared httpx transport.
Authenticated model listing and OAuth token/revocation requests also disable
redirects.

Credential persistence is Windows DPAPI only. Other platforms fail explicitly;
there is no plaintext/Base64 fallback. Legacy DPAPI records migrate to separate
registrations keyed by issued client ID. Unreadable stores fail without being
overwritten. A process lock serializes credential mutations and rotating refresh
tokens; refresh reloads the current disk record under that lock.

Sign-out attempts remote refresh-token revocation, clears local tokens, and
preserves the account/client mapping and host ID. Failure to confirm revocation
is reported. Selecting a signed-out registration reauthorizes that registration.
Quota and session states are attached to the account used by the request, so
switching accounts cannot attribute an older request's failure to the new account.

## Inference and supported settings

HTTP inference sends full context with `store=false` and `stream=true`.
System messages become ordered developer messages. Text, user images and
inline files survive conversion; unsupported media fail explicitly. Function
call/result history retains call IDs. Explicitly supplied function tools are
namespaced and serial; their output is normalized to NeuroMita's existing
`StructuredResponse.tool_call` so execution stays with ModelController.
Unadvertised tools and multiple calls in one response are rejected.

The dedicated `chatgpt-plan` settings schema exposes optional reasoning effort
and text verbosity. Availability depends on the selected model. Protocol metadata
declares migration from the old generic settings schema. `temperature`, `top_p`,
token limits and persistent HTTP response references are omitted. Other provider
schemas and wire protocols retain their existing behavior.

Responses events use the shared SSE parser and stream event channel.
Completion requires `response.completed`; failed/incomplete/error/interrupted
streams remain errors. Text and function argument deltas mark response progress,
preserving the runner's existing protection against fallback after visible output.

## Validation and boundaries

Automated checks use mock OAuth/HTTP responses, real preset resolution and runner
routing, offscreen Qt widgets, and real Windows DPAPI persistence. No live browser
sign-in, paid/subscription inference, headset or Unity testing is claimed.

Remaining acceptance checks: browser OAuth with a real account; account-specific
model catalog; live image/file inference; supported model settings; application
tool execution and quota failure behavior against the remote service.

Hosted tools, custom free-form tools, audio/video, and non-Windows credential
storage are outside this implementation. The app's existing structured-output
tool flow remains available; the adapter also accepts explicitly supplied native
function definitions. It does not add automatic native-tool discovery.

Sources verified on 2026-10-10:

- [Models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
- [Preview requirements](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
- [Account lifecycle](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)

The general project test suite is not green: root discovery includes bundled
dependency tests; the bundled Python 3.12 environment lacks compatible PyQt;
the project-wide Python 3.11 run recorded failures and ended around 58% without
a pytest summary. Collection also reports the pre-existing missing
`ui.widgets.dialogue_runtime_inspector` module. The final targeted test result
is recorded in the implementation plan.
