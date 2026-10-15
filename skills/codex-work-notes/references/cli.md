# CLI and record reference

Use the `scripts/notes.py` bundled with this skill. The examples below use an absolute project root and explicit task. Replace the example paths and task ID before running them.

```sh
NOTES=/absolute/path/to/codex-work-notes/scripts/notes.py
PROJECT=/absolute/path/to/project
TASK=retry-timeouts

python3 "$NOTES" --root "$PROJECT" --task "$TASK" init --objective 'Fix retry timeouts'
python3 "$NOTES" --root "$PROJECT" --task "$TASK" add --kind constraint --actor user --text 'Preserve the public API' --source 'User request in this task'
python3 "$NOTES" --root "$PROJECT" --task "$TASK" brief --max-bytes 6000
```

## Commands

| Command | Use |
| --- | --- |
| `tasks` | Inventory task IDs with `--root` but no `--task`; never choose a task automatically. |
| `init --objective TEXT` | Initialize task state with a short goal; store restrictions separately as constraints. |
| `add --kind KIND --text TEXT` | Append one record; use `--actor`, `--status`, and `--source` to qualify it. |
| `batch --file PATH` | Append a JSON array transactionally. |
| `brief --max-bytes N` | Read the current bounded agent view. The budget measures complete output bytes; token estimates are approximate. |
| `pending --offset N --limit N` | Page through active record IDs and snippets when more context is needed. |
| `get ID [ID ...]` | Retrieve up to 100 exact records in one call. One ID returns an object; multiple IDs return a list. |
| `recall --query TEXT` | Find relevant records. Search is a navigation aid; inspect current state and corrections before relying on a result. |
| `render --max-bytes N` | Write brief, human map, and manifest from one revision. |
| `doctor` | Inspect store integrity, scope, and evidence conditions. It does not certify the task's correctness. |
| `hook` | Read one host hook payload from stdin. |
| `hook-config` | Print optional configuration for inspection and manual merging. |

Optional `add` flags are `--id`, `--actor`, `--status`, `--source`, `--file`, `--depends-on`, and `--supersedes`. Repeat the last three flags for multiple values. `--file` records the hash of an exact existing path relative to the root. Preserve the command's returned event ID for later relationships.

## Checkpoint batch

`batch` accepts a plain JSON array. Each item is one event. Explicit IDs let a checkpoint reference its own records and make identical delivery idempotent. Reusing an ID for different content is an error.

```json
[
  {
    "id": "retry-decision-1",
    "kind": "decision",
    "text": "Keep retry limits unchanged; the observed timeout comes from the cancellation path.",
    "actor": "agent",
    "status": "asserted",
    "source": "Investigation of src/retry.py; supporting check is retry-check-1"
  },
  {
    "id": "retry-check-1",
    "kind": "check",
    "text": "The targeted cancellation regression failed before the patch.",
    "actor": "agent",
    "status": "failed",
    "source": "Recorded test output for this task"
  },
  {
    "id": "retry-next-1",
    "kind": "next",
    "text": "Patch cancellation cleanup and rerun the targeted regression.",
    "actor": "agent",
    "status": "asserted",
    "depends_on": ["retry-decision-1"]
  }
]
```

The strings above illustrate the format. Replace them with evidence actually observed in the current task; a descriptive source label is not independent verification.

Event fields: `id`, `kind`, `text`, `actor`, `status`, `source`, `occurred_at`, `evidence`, `depends_on`, `supersedes`, and `metadata`. Omit unused optional fields. File evidence is an array of objects such as `{"path":"src/retry.py","sha256":"…"}`; use `add --file` when a hash should be computed rather than supplied. Keep source time separate from capture time; omit an unknown source timestamp.

Kinds: `objective`, `constraint`, `decision`, `action`, `check`, `question`, `blocker`, `next`, `coverage`, `note`.

States: `asserted`, `observed`, `attempted`, `running`, `passed`, `failed`, `reverted`, `resolved`, `unknown`. A status describes the record's evidence, not a universal completion verdict. Preserve failed attempts when a later check passes.

## Corrections and dependencies

Append a replacement record of the same kind with `supersedes: ["OLD_ID"]`. A later inference cannot replace a user objective, constraint, or decision. User actor labels require an actual user source; the CLI does not authenticate who wrote them.

If two records independently replace the same earlier record, the conflict remains visible. Reconcile it explicitly, citing the chosen authority, rather than silently choosing the most recent timestamp. Use `depends_on` when an action or next step relies on a particular decision; replacing that decision marks dependent guidance stale transitively.

## Files and recovery

State lives under `.work-notes/codex/events.sqlite3`, with tasks isolated inside the database. Generated views use `.work-notes/codex/views/<task>/r<revision>-b<max-bytes>/`; `current.json` identifies the published revision. Read the paths returned by `render`. Different byte budgets produce distinct view directories. If existing generated bytes were modified, rendering fails rather than overwriting them. Preserve and move that revision directory aside before regenerating; do not edit generated views as a way to correct the record.

The local state directory contains its own ignore file. Notes can contain private project information; review any explicit export before sharing it. The content chain detects accidental history changes, not authenticated authorship or resistance to deliberate rewriting.

When a brief overflows, page through `pending`, retrieve relevant IDs together with `get ID [ID ...]`, and inspect applicable constraints before the affected action. Do not treat a short brief or an empty search result as proof that no constraint exists.
