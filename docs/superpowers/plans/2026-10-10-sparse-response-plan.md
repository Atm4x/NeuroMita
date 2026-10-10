# Sparse Response Implementation Plan

> Execute inline using superpowers:executing-plans in the same worktree, on codex/sparse-structured-response branched from 655d023c. User requested a separate branch and implementation commit.

**Goal:** Eliminate unused nullable/default output fields while preserving strict schemas and internal behavior.

**Architecture:** Compile a sparse wire DTO from the request profile and full model, validate and normalize it at ingestion, and generate provider schemas and prompt guidance from the same DTO.

**Tech Stack:** Python, Pydantic v2, application DSL, pytest.

**Spec:** [Sparse response design](../specs/2026-10-10-sparse-response-design.md)

## Constraints and review focus

Preserve existing handlers, persisted output, Unity contract, custom constraints, secret decisions, repair/trust semantics and non-character control-plane schemas. Do not issue paid requests. Reject mixed wire formats, malformed event payloads, duplicate scalar events and invalid segment indices. Recompile the tool catalogue from the continuation profile.

## Tasks

- [x] Add sparse DTO/compiler, strict schema conversion, event normalizer and local contract tests in `src/schemas/sparse_structured_response.py` and `src/utils/Testing/test_sparse_structured_response.py`.
- [x] Integrate parser ingestion and all existing schema adapters; cover legacy and GameMaster behavior.
- [x] Integrate sparse prompt contract after template intent resolution, skip the old shared catalogue for sparse requests, and refresh continuation guidance at tool depth.
- [x] Run focused parser/schema/prompt/provider tests and inspect scope and whitespace.

## Verification and delivery

The focused parser/schema/prompt/provider/stream/history suites passed: 194 tests and 3 subtests. After the final prompt-only refinements (reply limits and working-state shape), the affected sparse/prompt/parser subset passed again: 79 tests. Python compilation and whitespace checks passed. Provider payload checks use local mocks; no live provider calls were issued.

Deliver as a separate commit on `codex/sparse-structured-response`, push it, and open a dependent PR targeting `codex/structured-response-capabilities`; do not merge. The worktree stays at its original path.
