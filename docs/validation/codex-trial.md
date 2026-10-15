# Codex skill instruction-following trial

Scope: a Codex evaluator followed the installed Codex skill on supplied synthetic history. No native hooks, live project, model API, deployment, installation, settings change, or commit was exercised. Only this trial directory was written; product implementation, tests, research, intended outputs, and other agents' work were not read.

## Procedure and exact command outcomes

Read SKILL.md and its references/cli.md. Created a canonical isolated project root and a 16-record events.json directly from the synthetic history. Located notes.py relative to the skill as instructed. Every CLI call passed the explicit root and stable task ID retry-timeouts.

CLI invocations: 14 total, all exit 0: init (1); batch (1); render --max-bytes 1000 (1); doctor (1); pending --offset 0 --limit 20 (1); get for each of nine omitted active records (9). The nine IDs were framework-vitest, core-read, retry-test-failed, retry-edit-reverted, backoff-edit, backoff-test-p7, git-capture-failed, completion-claim, and continue-work. No retries were needed.

Shell/tool command calls: 18 through validation; 19 including writing this report. Elapsed wall-clock time from reading SKILL.md through validating all nine retrieved records: 116.166 seconds. Report-writing and later Claude exercise are excluded.

## Outputs

- Input notes: events.json (16 records), plus the init-generated objective (revision 1).
- Persistent notes: .work-notes/codex/events.sqlite3; final revision 17.
- Brief: .work-notes/codex/views/retry-timeouts/r17-b1000/brief.md, 996 UTF-8 bytes.
- Full human map: .work-notes/codex/views/retry-timeouts/r17-b1000/map.md, 9092 UTF-8 bytes.
- Manifest: .work-notes/codex/views/retry-timeouts/r17-b1000/manifest.json, 509 UTF-8 bytes.

The byte cap applies to the brief. The map intentionally retains the complete history.

Doctor returned coverage=partial, ledger_errors=[], evidence=[], view_stale=false, and view_errors=[]. It explicitly stated that integrity and file-state checks do not prove truth, authorship, or completion.

## Usability findings

No command execution failure occurred. Instructions were sufficient to initialize, batch, render, diagnose, and recover records without reading implementation.

The 996-byte brief omits nine active records, including the controlling Vitest decision, current backoff edit, pending p7 test, reverted retry attempt, earlier failed test diagnostic, Git permission-denied blocker, unsupported completion claim, and continuation step. It spends space repeating public API, zero-retry, and deployment constraints already present in the objective. Therefore the compact brief alone cannot support accurate operational continuation. This is disclosed by its OVERFLOW footer; pending then get successfully recovered all omitted records, but required ten additional CLI invocations. This is an observed compression/usability limitation, not silent data loss.

The human map includes current records, all 17 historical records, actor/status/source annotations, correction relationships, and the next-step dependencies. Superseded Jest/Mocha decisions and the original attempted retry edit remain visible in history. No latest-test pass or implementation-complete outcome was inferred.

## Missing evidence and interpretation limits

Source code, patches, actual test commands, final p7 output, final Git diff, and approval/deployment outcomes were absent from the source history. None was invented. Source timestamps are unavailable; capture timestamps are present. Actor labels and descriptive source strings are assertions rather than authenticated evidence. The init objective is labeled agent, so the user-authored constraints were also recorded explicitly with user actor labels.

The evaluator deliberately encoded the chronology, statuses, correction links, and caveats; the skill did not infer these from raw conversation. This result tests documented manual CLI instruction following, not automatic capture or native Codex integration. It does not establish that the synthetic retry implementation is correct or complete.
