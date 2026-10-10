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

## Strict-schema and changing-state controls on 2026-10-10

The user authorized further investigation. First performed four calls in two
delayed pairs, with the same account/model and the application's strict
`StructuredResponse` schema. Then announced and performed two single-call
controls on the warmed dialogue context. No more calls were made in this stage.
All six responses completed and parsed successfully. Image placeholders remained
replaced with fixed text; generated actions were not executed.

| Request | Input tokens | Cached tokens | Delay after baseline completion |
| --- | ---: | ---: | ---: |
| Synthetic reference + strict schema, first | 4,978 | 0 | — |
| Same synthetic request, repeat | 4,978 | 0 | 99.661 s |
| Saved dialogue + strict schema, first | 12,289 | 0 | — |
| Same dialogue request, repeat | 12,289 | 12,032 | 101.983 s |
| Change only final user message; retain first 36 items | 12,290 | 12,032 | 207.680 s |
| Change only state block at zero-based item 28; retain first 28 items | 12,299 | 0 | 310.917 s |

Baseline request hashes, account and model were verified identical within each
pair. The last two controls retained the baseline's output schema and all other
settings; only the stated input item changed. All compared responses returned
server diagnostics `{"type":"unavailable"}`.

These measurements show that strict output schemas do not categorically disable
subscription caching. A roughly 100-second delay did not guarantee a hit on the
shorter schema-bearing request, so a publication delay alone is not a sufficient
explanation. The shorter miss does not establish a model-specific token threshold.

Changing a state block before the end of the previously cached context reproduced
a complete miss, whereas changing only the final prompt preserved 12,032 cached
tokens. This is evidence that the current implicit cache path did not reuse the
long common prefix in the state-change control; it is not proof that every such
change always causes a miss or that server routing/eviction played no role.

Actual saved application requests at 10:36:26.939 and 10:37:55.152 UTC contain 34
and 36 messages. Their first 26 messages match; afterward history grows and
system-state, memory and environment content changes. The matching first 26
messages contain an estimated 7,693 text tokens, including 7,389 in the initial
13 developer messages (estimates exclude original screenshot payloads). This
matches the failure pattern tested above: volatile state arrives before the
final user prompt, so the preceding full request is not an unchanged prefix.

The next discriminating experiment is an explicit cache breakpoint at the end of
the stable initial developer block, followed by a state-changing request with
that breakpoint retained. Public subscription-route acceptance and cache reuse
with that control have not yet been tested. No artificial pause or automatic
breakpoint was added to application behavior.

## Explicit-control rejection and prefix-only warmup on 2026-10-10

Following the user's authorization to investigate explicit breakpoints, sent
one strict-schema dialogue request with a breakpoint on the final content block
of the initial 13 developer messages, and `prompt_cache_options` mode `explicit`
with TTL `30m`. The public subscription endpoint rejected it before generation:
HTTP 400, `invalid_parameter`, `prompt_cache_options is not supported on this model`.
Then sent a request containing only the content-block breakpoint, without the
mode/TTL options. It was also rejected before generation: HTTP 400,
`invalid_parameter`, `prompt_cache_breakpoint is not supported on this model`.
These were actual wire requests with the fields injected after adapter conversion;
the errors are not explained by our adapter dropping those fields.

The prior comparison-only `prompt_cache_options` requests were accepted, so the
mode/TTL rejection does not imply every member of that object is unsupported.
The marker-only rejection establishes that a manual breakpoint cannot currently
be used with this account/model/subscription route. The broader public API guide
describes such breakpoints, but that capability is absent in these live tests.

Then performed two announced generations without unsupported controls:

| Request | Input tokens | Cached tokens | Result |
| --- | ---: | ---: | --- |
| Only initial 13 stable developer messages, same strict schema | 9,276 | 8,960 | completed, valid structured JSON |
| Full 37-item dialogue, state block at item 28 changed, same initial 13 items | 12,299 | 0 | completed, valid structured JSON |

The full request started 109.920 seconds after the prefix-only response completed.
Account, model, initial-prefix hash and schema matched. Prefix SHA-256 was
`af177007931444e0997fe3cf7be5db7a0dddbbaf8faf478a148dadee27d55a6b`.
Prefix-only response ID:
`resp_02b6cfc0696214e9016aca1cd8d88887d29a42ad3ea7f30a5f`.
Full-response ID:
`resp_03274dd971078f4e016aca1d50584487d284d59fa5a8bd3650`.
The full response's server comparison again returned `{"type":"unavailable"}`.

The prefix-only request already reported a cache read; this is not evidence of a
new physical cache write. An available cached prefix did not translate into reuse
inside the larger dialogue in this control. Automatic prefix-only warmup is thus
not a verified workaround. No rejected cache controls or automatic warmup were
added to application behavior.

This stage contained two HTTP-400 requests and two successful generations.
It establishes subscription-route capability limitations and an unsuccessful
warmup control, not the server's internal routing/eviction policy. A subsequent
candidate workaround is to preserve the previous full request as an unchanged
prefix and append state updates and new turns, rather than rebuilding the volatile
suffix. That strategy still requires live validation and a design that keeps the
latest state authoritative and prevents unbounded context growth.

Sources: [OpenAI prompt caching and shared-prefix caveats](https://developers.openai.com/api/docs/guides/prompt-caching),
[subscription backend breakpoint reports](https://github.com/openai/codex/issues/35300),
[another Sign in with ChatGPT integration's cache measurements](https://dshmp.com/en/plugins/dsh-plugin-chatgpt).
