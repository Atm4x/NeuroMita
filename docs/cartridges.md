# Cartridge personalities

Unity owns the catalog and all gameplay state. Python does not ship an independently editable copy of the catalog. Each cartridge request supplies `context.cartridge` with version `1`, the Unity catalog, the inserted ID, a nonempty session token, and explicit `ai_enabled: true`. `hello_ack.cartridge_protocol_version` advertises support. Unknown versions and mismatched inserted/character IDs abort the request before character registration or generation.

`domain/cartridge_catalog.py` validates IDs, limits, mappings and known effect types. `CharacterManager.register_cartridges` installs factories for the single generic `CartridgeCharacter` implementation. Existing `Cart_portal`/`Cart_divan` IDs retain their character-scoped history keys. Other definitions use `Cartridge_<id>`. Registration and cartridge requests do not change the selected Mita or Unity's normal Mita target.

The existing create-task/model/history pipeline is reused. `services/cartridge_prompt.py` selects a short history tail and applies a character budget; it excludes the ordinary Mita DSL, RAG and world-state blocks. Cartridge generation disables tools, streaming voice output, TTS, background compression and core-memory triggers. Structured replies retain text and segment targets and drop gameplay instructions and memory mutations. Learning and activation remain explicit validated Unity operations.

Histories use the existing SQLite service. Saving keeps at most `historyMessages` active messages (2–40), independently for each cartridge. Unknown or temporarily removed Unity effect definitions do not require Python migrations because Python never owns the effect save.

Run `python -m unittest discover -s src/utils/Testing -p test_cartridges.py -v`. For a deterministic transport check, with the normal application stopped, run `python tools/cartridge_smoke_server.py`, then enter Play Mode in the paired Unity branch. The helper binds localhost:12345 for up to fifteen minutes, uses temporary histories, and returns clearly marked SMOKE replies. It exercises real request handlers, catalog registration, prompt construction, history and socket task updates; it does not test a real LLM provider.

The paired Unity work is on branch `Carteidges`; this Python implementation is on `codex/cartridge-system`. Built-in custom-content packages and independent voice profiles are not part of this version. New records using existing effect types are configured in Unity's `Assets/Resources/Cartridges/catalog.json` and delivered over the protocol.
