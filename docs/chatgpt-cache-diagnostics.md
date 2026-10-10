# Temporary ChatGPT plan cache diagnostics

The provider logs request/response metadata at INFO with the marker
`[ChatGPT cache diagnostic]` in `Logs/NeuroMitaLogs.log`.
No authorization headers, credentials or message bodies are logged.
Comparison retains only the previous request in memory; fingerprints and prefix
lengths describe canonical JSON characters, not model tokens.

Request records contain per-item hashes, the first changed item, the common
prefix, parameter hashes, account hash and interval since the previous request.
The overall settings comparison excludes the diagnostic comparison response ID.
Completed-response records preserve server cache counters, response/request IDs
and `prompt_cache_diagnostics`. Missing usage remains null rather than zero.
After a completed response, the next request on the same account/model includes
`prompt_cache_options.comparison_response_id`; it does not chain response content
or change cache lifetime. This is temporary instrumentation and can be removed
with the provider's `CacheDiagnostics` integration.

## Live verification on 2026-10-10

Used the configured `Codex` preset, `gpt-6-luna`, existing OAuth session, disabled
optional generation parameters and the latest saved dialogue context. Saved
image contents were redacted, so historical images were replaced with fixed
text placeholders. No generated tools or world actions were executed.

One initial request failed validation of a redacted image URL (HTTP 400).
Four successful requests followed, in two identical-input pairs. Each reported
12,289 input tokens, zero cached tokens and zero cache-write tokens. Generated
outputs contained 184, 175, 163 and 174 tokens. All completed and parsed as
`StructuredResponse`; strict `text.format` was accepted by the subscription route.
The first pair had all 37 input items and all settings/account fingerprints
identical, with 6.734 seconds between request starts.

The second pair used the first completed response ID for server comparison.
The server accepted that parameter and returned
`prompt_cache_diagnostics: {"type": "unavailable"}`. These observations exclude
changing client input/settings as the cause in this text-only reproduction, but
do not establish the server's internal reason or prove that zero write accounting
means nothing was physically cached. No further live requests were made.

Source: [OpenAI cache diagnostics](https://developers.openai.com/api/docs/guides/prompt-caching/diagnostics).

## Delayed text-only control on 2026-10-10

The user authorized a further two-call control on the same configured account
and `gpt-6-luna`. Used fixed synthetic reference text, one developer message and
one user message, no output schema, images, tools or optional model settings.
Both requests returned `OK` and reported 3,145 input and 5 output tokens.

- First response: zero cached tokens, response ID
  `resp_0d733b4674479555016aca196cb42087d2933eff61f67e1a86`.
- Second request began 94.150 seconds after the first completed. It reused the
  exact base request (SHA-256
  `3171055f8cf3cd083d4248df8b74ca0b7b251b2fa73a8cbab6f93f6d12d9d72d`)
  and added only the diagnostic comparison response ID. It reported 2,816 cached
  tokens (89.54%), zero cache-write tokens and diagnostics `{"type":"unavailable"}`.
  Response ID: `resp_021ee27f67978f8e016aca19cd774887d293089c6973daeded`.

This confirms cache reads on this account, subscription route and model.
Zero cache-write reporting does not establish that no physical write occurred.
Server diagnostics can remain unavailable even when usage reports a cache hit.
The control differs from the earlier dialogue probes in timing, input and output
format, so it does not isolate which of these explains the earlier misses.
No additional live calls were made in this control.
