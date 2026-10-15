# Work Notes Implementation Plan

**Goal:** Ship two standalone skills with reliable action records and consistent human/agent views.

**Architecture:** A standard-library event store and renderer copied into independent host packages. Separate adapters normalize documented hook events. Synthetic regression fixtures test the audited failure cases.

**Spec:** [SPEC.md](SPEC.md). The user approved the revised design and explicitly requested implementation; proceed without another design approval gate.

## Review focus

- Corrections must not bypass user constraints or leave stale dependent guidance active.
- Overflow must preserve exact retrieval paths without claiming complete coverage.
- Duplicate delivery and concurrent writing must neither lose events nor corrupt history.
- Host-specific payload failures must remain failures/unknown, never successful by default.
- A copied skill folder must work alone and never depend on the sibling agent or repository source.

## Execution

- [x] Core: failing behavioral tests, implementation, and full suite.
- [x] Capture: independent host normalizers and fixtures checked against official documentation.
- [x] Codex skill: concise entrypoint, metadata validation, and independent use scenario.
- [x] Claude Code skill: separate entrypoint, validation, and instruction-use scenario by a Codex evaluator; native Claude trial remains outstanding.
- [x] Packaging: standalone distributions, instructions, example maps, CI, and validation tooling.
- [x] Research: evidence and actionable improvements, with hypotheses distinguished from measurements.
- [x] Review: independent review, fixes, full checks, and recorded limitations.

## Progress and decisions

- Initial baseline agent produced a 939-byte brief retaining the supplied constraints, pending check, and capture error without a new skill. This is a successful qualitative control, not evidence of baseline failure or superiority of our proposed skill.
- Scope decision: ongoing research only during active development, per user clarification. No recurring automation.
- Publication decision: user selected a new public repository named `agent-work-notes`. The distribution license is not inferred.
- Review fixes: working-directory-aware evidence, generated-view byte verification, and linear-space correction-chain handling.
- Trial improvement: multi-ID retrieval replaces repeated lookups; short objectives avoid duplicating constraint records.
