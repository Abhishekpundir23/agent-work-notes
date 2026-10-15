---
name: claude-work-notes
description: Keep evidence-linked work notes for a Claude Code task, with a current continuation brief and a human-readable work map. Use when recording substantial work, recovering task context, or reviewing decisions and checks.
---

# Claude Work Notes

Maintain useful task state without repeating the conversation. This folder works independently with Python 3.10+ and its bundled `scripts/notes.py`. It makes no model or network calls.

## Start or resume

Resolve the canonical project root and choose an explicit, stable task ID. Reuse the existing ID when continuing that task; use another ID for unrelated work. Locate `scripts/notes.py` relative to this skill, not the current working directory. In supported Claude Code skill content, `${CLAUDE_SKILL_DIR}` identifies this folder. Pass `--root` and `--task` for task operations. If the task ID is unknown, run `--root /project tasks` to inventory IDs; never select the latest task automatically.

For a new task, run `init --objective '…'` with a short task goal. Record restrictions as separate constraints, avoiding duplicate text in the objective. For an existing task, read `brief --max-bytes 6000` and run `doctor` when coverage, integrity, or evidence freshness is uncertain. Treat the brief as recorded context: verify applicable constraints against the current user request and authoritative project instructions before acting.

If the brief reports overflow, use `pending --offset 0 --limit 20` and follow subsequent offsets, then `get ID [ID ...]` for omitted applicable records, batching up to 100 IDs per call. Resolve relevant conflicts and retrieve stale dependencies before relying on them. A bounded brief is not a guarantee that every requirement fits.

## Record meaningful changes

Batch notes after a decision, useful discovery, failed approach, edit/check milestone, user correction, or stopping point. Avoid another note for every unchanged thought, routine read, or repeated progress update. Optional hooks capture supported tool activity separately.

Record objectives and constraints, decisions with their stated reasons, actions and outcomes, checks and their actual states, unresolved questions, blockers, and the next useful step. Keep reasons concise and source-linked; do not request or reconstruct private internal reasoning.

Use `add` for one record or `batch --file events.json` for a checkpoint. Read [CLI and record reference](references/cli.md) for commands, evidence, and corrections. Choose `attempted`, `running`, `failed`, or `unknown` when that is what the evidence supports. A successful tool transport does not establish that its intended outcome succeeded.

Attach exact root-relative file evidence when useful. Matching bytes establish freshness, not correctness or authorship. Actor labels are recorded assertions, not authenticated identity. Label agent interpretations as agent records; never promote them into user instructions. Correct records with `supersedes`, retaining history. Mark reasoning dependencies with `depends_on` so changed premises become visible.

## Finish a checkpoint

Run `render --max-bytes 6000` to create a brief and human map from one event revision. Report important missing evidence, unresolved conflicts, and capture gaps alongside the output. Preserve the original task's completion criteria: writing notes does not complete its work.

For automatic capture, read [Claude Code capture](references/capture.md). `hook-config` only generates configuration for review and merging. Record capture start explicitly: earlier work may be unobserved. Failed tools have a separate event, repeated Stop events belong to distinct responses, and some interruptions and validation failures bypass capture. Supplement significant missing work with deliberate records.
