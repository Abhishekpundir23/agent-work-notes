# Validation of v0.1

Measured locally on 2026-10-15 with Python 3.12.13 on macOS arm64. This is an experimental release. These checks do not establish lower total model cost or improved real task success.

## Deterministic checks

`python3 -m unittest discover -s tests -v`: **65 tests passed**.

Coverage includes independent copied skill folders, transactional batches, parallel writers, stable retry delivery, distinct changed observations, multi-step corrections, conflicting corrections, stale dependencies, user-constraint protection, whole-brief UTF-8 bounds, overflow recovery, task discovery/isolation, exact evidence, hook working directories, timestamps, failure/unknown handling, repeated Stop events, view integrity, and local-state Git exclusion.

Tests began with failing cases before implementations or fixes. `python3 tools/build.py --check` verifies bundled copies. Both SKILL.md files passed the supplied skill-creator validator. Its PyYAML dependency was isolated outside the project; the skills require only Python's standard library.

## Independent instruction-following exercises

| Exercise | Brief bytes | CLI calls | Elapsed through validation |
| --- | ---: | ---: | ---: |
| Codex skill, followed by a Codex evaluator | 996 | 14 | 116.166 seconds |
| Claude instructions, followed by the same Codex evaluator | 997 | 14 | 104.450 seconds |

Both used supplied synthetic history in separate project roots. All calls succeeded; maps preserved failed/reverted attempts, corrected decisions, pending checks, and missing evidence. The evaluator manually entered the records; the skill did not automatically extract them from conversation.

The tight 1,000-byte briefs omitted nine active records. Overflow was visible, but the original interface required nine separate `get` calls. The revised interface retrieves those IDs together in one call, verified by a CLI regression. Skill guidance now avoids repeating constraints in the objective. These changes have not established a lower total token cost or better task completion.

The no-skill control produced a 939-byte brief retaining the supplied constraints, pending test, and capture error. It was a successful qualitative baseline. Trials were not randomized, repeated, or independent across models; their timings are not comparative performance results.

Raw accounts: [Codex trial](validation/codex-trial.md), [Claude instructions trial](validation/claude-instructions-trial.md), [baseline brief](validation/baseline-brief.txt).

## Independent code review

Three findings were reproduced, fixed with regression tests, and independently rechecked:

1. Relative tool file paths now resolve against the hook's working directory.
2. Cached views are verified before reuse. Modified bytes produce an explicit failure.
3. Correction processing propagates active terminal IDs instead of retaining complete historical ancestry. The reviewer's 4,000-record linear-chain fixture dropped from approximately 374 MB peak process RSS to 28 MB. This includes process overhead; it is not a model-memory measurement.

## Local overhead sample

`python3 tools/benchmark.py --events 5000 --runs 3` measured 5,002 synthetic records. Median batch append time was about **87 ms**, fresh brief generation **20 ms**, and full map/brief rendering **44 ms**. The brief was 5,965 bytes under a 6,000-byte cap. See [raw measurements](local-benchmark.json).

This excludes per-tool process startup, host scheduling, model reading/writing, token costs, and actual task success. Full history stays on disk; only the brief is bounded. These measurements do not prove memory is cheaper than native context.

## Not yet established

- Native Codex or Claude Code skill discovery and hooks in an authenticated provider-backed task.
- Complete automatic capture; some events are unavailable or bounded/redacted.
- Native compaction, interruption, permission-denial, and replay behavior on each host version.
- Total task/token efficiency against native continuation, manual notes, or competing tools.
- Global novelty or production readiness.

CI defines Python 3.10 and 3.12 runs on Linux. Local execution above is not a claim those remote jobs have run. Research continues during active development; changes should follow reproduced failures or measured hypotheses.
