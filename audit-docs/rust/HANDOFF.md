# Handoff: Rust core contracts

## Start here

This directory is the standalone Cargo project. Enter it before running Cargo so .cargo/config.toml replaces crates.io with vendor/:

```sh
cd audit-docs/rust
cargo test --locked --offline
cargo clippy --locked --offline --all-targets -- -D warnings
cargo fmt --all -- --check
```

Rust 1.89+ is required by the locked dependency set (uuid requires 1.89). Verified on Rust 1.99.1 / Windows MSVC. Native TLS dependency aws-lc-sys needs a working native build environment; vendor supplies crate sources, not the Rust/C toolchains. Linux web-agent compilation has not been run on this Windows host.

Tokio has full features. All locked crates, including platform-specific sources and licenses, are in vendor/. Do not normalize line endings there: Cargo verifies checksums. .gitattributes preserves bytes. target/ is intentionally excluded.

## Architecture

Read [minimal-contracts](../future/minimal-contracts.md) and [checklist](../future/implementation-checklist.md). These supersede limitations of the historical first-slice.md.

- Static ChatApi/SettingsApi/CharacterApi, explicitly initialized once per process. No service locator and no silent fallback presets.
- One owned Character per CharacterHandler mailbox; immutable definition and mutable state. CharacterRegistry exposes handles.
- MessageHandler owns sequential execution per character; different characters run concurrently. No LLM await under global locks.
- GenerationPreset contains typed ProviderTemplate. Gemini wire/URL/auth are inside generation/gemini, not in common application/presenter code.
- Gemini authentication matches the original Python google_gemini_default: URL query parameter key, not x-goog-api-key. Keep URL encoding and redaction; never log the authenticated request URL.
- Generation returns ProposedResponse with effects. Request lifecycle and internal acceptance phase are separate. Cancellation competes atomically with entry into Accepting; effects precede Finished and the next request.
- Independent GuiPresenter exposes commands and bindable settings; frontend bindings only translate input/output. No Slint dependency yet.
- ServerLifecycle owns TCP clients and routes commands to Api. It is generic across client implementations.

## Useful files

| Area | Files |
|---|---|
| Composition/lifecycle | src/app.rs, src/lifecycle.rs |
| Static entry points | src/api.rs, src/settings/mod.rs |
| Requests and observation | src/request/ |
| Characters/context | src/character/, src/timeline.rs |
| Provider port and Gemini | src/generation/ |
| Voice port | src/voice.rs |
| Settings/storage | src/settings/ |
| Presenter/binding | src/presentation/ |
| Network | src/server.rs |
| Console | src/main.rs, src/terminal.rs |
| Contract scenarios | tests/contracts.rs, tests/vertical_slice.rs |

Tests initialize static Api once per test process; do not add many parallel integration test functions that each start a different application in the same process. Local tests do not need credentials or external network access.

## Live provider status

One live Gemini attempt used an explicit local fixture, read by tests/live_gemini.rs. No credential is in the repository. It failed before an HTTP response; independent curl to Google's API host also timed out. Do not infer invalid credentials or rotate anything.

To opt into another live run, provide NEUROMITA_LIVE_GEMINI_PRESET_FILE and NEUROMITA_LIVE_GEMINI_PRESET_ID for an explicitly selected local JSON fixture, then run:

```sh
cargo test --locked --offline --test live_gemini -- --ignored --nocapture
```

The fixture is a legacy test-data source only. Production code uses typed presets and does not discover/import/rotate a catalog.

## Remaining work / deliberate limits

- Re-run live Gemini in a network environment that reaches Google.
- Real TTS engine, Slint/TUI frontend, tools and multimodal/streamed token handling are not implemented; ports and settings contracts are present.
- Timeline is a Vec with one branch and minimal at; no database, forks/checkpoint recovery or durable effect transaction.
- RequestTrace is bounded memory diagnostics. No durable DB trace or cross-restart request recovery.
- Discovery can lag, and network receipts have a bounded per-connection lifetime. No reconnect-wide deduplication/authentication/compatibility with the old Unity wire protocol.
- Character state currently has the minimal accepted-reply effect. Extend typed effects and their owner-side validation, not UI mutations.

Keep working toward the user's contracts rather than copying Python architecture. Do not fix or refactor Python/Unity files as part of this Rust task.

## Git delivery

Target branch: codex/rust-core-contracts on origin. Final pushed commit is reported in the chat; check git log and the checklist for delivered state.

Implementation/vendor commit e87d392ca327f3e6f50302051458498af0e84bb5 was pushed and matched the remote ref. A following documentation-only commit records this delivery. Final local validation: 8 tests passed, one opt-in live test ignored, Clippy and rustfmt passed; all 168 vendor package checksums verified. Existing untracked build archives were deliberately left out.

Subsequent Gemini auth fix matches Python's query key contract. Validation after that fix: 9 local tests passed, Clippy/rustfmt passed; HTTP fixture asserts query authentication and absence of auth headers.

The live fixture was retried after the query-auth fix with the same explicit preset. It still failed before an HTTP response (transport error); credentials/model validity remain unconfirmed. The authenticated URL was not printed or persisted.
