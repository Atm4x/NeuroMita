# Sparse structured response design

The requested improvement implements the referenced conversation's compact wire DTO and normalizer after the request-capability work in commit 655d023c.

## Contract

- Every character reply has `segments: [{text: string}]` and `events: [...]`. An ordinary reply has an empty event array.
- Each list operation is one event with `type` and `value`. Segment operations additionally require a zero-based `segment` index. Scalar events occur at most once per field/segment; duplicates are rejected rather than silently overwritten.
- Existing internal field names are event identifiers. Intent events carry `intent_type` and a JSON object encoded in `payload`; tool events carry `name` and JSON object encoded in `args`. Arbitrary object payloads are strings on the strict wire so every advertised object has a closed, finite shape.
- Enabled reasoning and custom parameters remain dedicated root fields. An unresolved secret remains a required nullable root decision, preserving the reveal-state fix. Working state and image descriptions are events.
- Event variants are compiled from the immutable request profile and the internal model annotations. Disabled variants are absent from the schema.

## Boundaries

`SparseStructuredResponse` validates the wire; its normalizer produces the existing full `StructuredResponse`. The parser accepts both formats, retains repair/trust metadata, and rejects invalid sparse operations before character processing. Internal handlers, persisted structured result data, and Unity protocol version remain unchanged.

The shared response-format DSL skips its legacy field catalogue for sparse requests. PromptController adds the generated sparse contract after discovering the template's intent support. Legacy field instructions elsewhere describe the same semantics; the sparse contract explains their translation to events.

All current schema adapters select the same wire DTO. OpenAI receives nested `anyOf` with all object properties required and `additionalProperties: false`; Gemini receives JSON Schema with the union preserved. GameMaster's separate control-plane model is not converted. Retry/fallback keep the profile; tool continuation selects the next-depth event catalogue.

Native tool calling remains in the existing provider pipeline. This change makes structured tool calls sparse without adding a new Responses/OAuth provider or migrating independent provider tool loops.

## Acceptance

Validate compact neutral replies, memory/stats/actions normalization, segment ordering, dynamic custom parameters, required nullable secrets, disabled variants, duplicate scalars, malformed JSON payloads, repaired-response trust, legacy compatibility, provider payloads, rendered prompts and tool depth. Use only local tests; no paid calls.
