# Claude skill instruction-following trial

Scope: a Codex evaluator followed the Claude skill instructions on supplied synthetic history. This was not a live Claude or Claude Code runtime. No native hooks, live project, model API, deployment, installation, settings change, or commit was exercised. Only this trial directory was written. Product implementation, tests, research, intended outputs, and other agents' work were not read.

## Procedure and exact command outcomes

Independently read this skill's SKILL.md and references/cli.md. Created a new canonical project root and transcribed the synthetic history into 16 records in events.json. Used the skill's actual bundled notes.py through its absolute path; the Claude-only CLAUDE_SKILL_DIR variable was not available or needed for this manual exercise. Every CLI call passed root and task retry-timeouts explicitly. No Codex notes database or output was loaded into the Claude trial.

CLI invocations: 14 total, all exit 0: init (1); batch (1); render --max-bytes 1000 (1); doctor (1); pending --offset 0 --limit 20 (1); get for each of nine omitted active records (9). The nine IDs were framework-vitest, core-read, retry-test-failed, retry-edit-reverted, backoff-edit, backoff-test-p7, git-capture-failed, completion-claim, and continue-work. No retries were needed.

Shell/tool command calls: 18 through validation; 19 including writing this report. Elapsed wall-clock time from reading this SKILL.md through validating all nine retrieved records: 104.450 seconds. Report-writing is excluded. The same evaluator had already completed the Codex trial, so elapsed times are not an independent performance comparison between models or hosts.

## Outputs

- Input notes: events.json (16 records), plus the init-generated objective (revision 1).
- Persistent notes: .work-notes/claude/events.sqlite3; final revision 17.
- Brief: .work-notes/claude/views/retry-timeouts/r17-b1000/brief.md, 997 UTF-8 bytes.
- Full human map: .work-notes/claude/views/retry-timeouts/r17-b1000/map.md, 9093 UTF-8 bytes.
- Manifest: .work-notes/claude/views/retry-timeouts/r17-b1000/manifest.json, 510 UTF-8 bytes.

The byte cap applies to the brief. The map intentionally retains the complete history.

Doctor returned coverage=partial, ledger_errors=[], evidence=[], view_stale=false, and view_errors=[]. It explicitly stated that integrity and file-state checks do not prove truth, authorship, or completion.

## Usability findings

No command execution failure occurred. Instructions were sufficient to initialize, batch, render, diagnose, and recover records without inspecting implementation. This does not establish native Claude compatibility.

The 997-byte brief omits nine active records: the Vitest decision, unchanged core.py read, failed retry test diagnostic, reverted retry edit, latest backoff edit, still-running p7 test, Git permission-denied blocker, unsupported completion claim, and continuation step. The brief repeats public API, zero-retry, and deployment constraints already present in the objective. It therefore cannot serve alone as an operational handoff. Its OVERFLOW footer discloses the omissions, and pending plus nine get calls recovered all of them, costing ten additional CLI invocations. This is an observed bounded-brief usability limitation, not silent data loss.

The full map preserves all 17 records, superseded framework decisions, the attempted and reverted retry edit, the historical failed test, current unresolved test, Git capture gap, and unsupported completion claim. It also retains explicit actor, status, source, correction, and dependency information. No verified completion or latest-test passing result was inferred.

## Missing evidence and interpretation limits

Actual source contents, patches, test commands, final p7 result, final Git diff, and approval/deployment outcomes remain absent. No source timestamps or file hashes were invented. Descriptive source strings and actor labels are assertions, not authenticated evidence. The init objective is agent-labeled, while the controlling user constraints were explicitly entered as user records.

The evaluator supplied chronology, statuses, correction relationships, and evidence caveats manually. The skill did not extract them from raw conversation. Native Claude skill discovery, CLAUDE_SKILL_DIR expansion, hooks, interruptions, and automatic capture were not tested. This exercise supports only manual instruction-following and documented CLI behavior in the available environment.
