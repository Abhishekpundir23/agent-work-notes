# Work Notes v0.1

Build two independently installable local skills: `codex-work-notes` and `claude-work-notes`. There is no cross-agent synchronization or dependency. A shared development source is copied into each distribution, so either folder works alone.

The core is Python 3.10+ standard library. Store append-only structured events in SQLite under `<project>/.work-notes/<host>/events.sqlite3`, isolated by explicit task ID and bound to the canonical project root. A local `.gitignore` inside the owned state directory prevents accidental tracking. No model service, embeddings, network, package install, or global configuration modification is required.

Each event records `id`, `kind`, `text`, `actor`, `status`, optional source timestamp/reference, exact file evidence, dependencies, corrections, and bounded metadata. Caller-provided actors are assertions, not authenticated identities. No private reasoning is captured. Evidence presence or a matching hash does not prove correctness or authorship.

Kinds: objective, constraint, decision, action, check, question, blocker, next, coverage, note. States: asserted, observed, attempted, running, passed, failed, reverted, resolved, unknown. A later event can supersede earlier events of its own kind. Model/tool records cannot supersede user constraints/objectives/decisions. Conflicting sibling corrections stay visible until an explicit correction reconciles them. Dependencies on superseded records mark dependent records stale transitively.

The current brief and human Markdown map are generated from one event snapshot. Whole-output byte budgets are exact; token estimates are labelled estimates. Overflow is explicit with IDs for exact retrieval. The skill must retrieve omitted applicable constraints before acting. The work map preserves history, relationships, stated reasons, and source references; it is not private internal reasoning.

CLI (each independent `scripts/notes.py` chooses its own host):

```
python3 /path/to/notes.py --root /project tasks
python3 /path/to/notes.py --root /project --task retry init --objective 'Fix retries'
python3 /path/to/notes.py --root /project --task retry add --kind constraint --actor user --text 'Preserve public API'
python3 /path/to/notes.py --root /project --task retry batch --file events.json
python3 /path/to/notes.py --root /project --task retry brief --max-bytes 6000
python3 /path/to/notes.py --root /project --task retry pending --offset 0 --limit 20
python3 /path/to/notes.py --root /project --task retry get EVENT_ID [EVENT_ID ...]
python3 /path/to/notes.py --root /project --task retry recall --query retries
python3 /path/to/notes.py --root /project --task retry render --max-bytes 6000
python3 /path/to/notes.py --root /project --task retry doctor
python3 /path/to/notes.py --root /project --task retry hook < hook-event.json
python3 /path/to/notes.py --root /project --task retry hook-config
```

`tasks` is the only command that does not require `--task`; it inventories IDs and never automatically selects the latest. `get` accepts up to 100 IDs, returning an object for one ID or a list for multiple IDs. Keep the objective short and record restrictions separately as constraints.

Generated views live under `.work-notes/<host>/views/<task>/r<revision>-b<max-bytes>/`, with a `current.json` pointer. The byte budget is part of the directory identity. Rendering fails if an existing generated file was modified; preserve and move that directory aside before regenerating.

Core API: `Store(root, host, task)`, `.initialize(objective)`, `.append(event)`, `.append_many(events)`, `.events()`, `.get(id)`, `.tasks()`, `.state()`, `.recall(query, limit=8)`, `.brief(max_bytes=6000)`, `.render(max_bytes=6000)`, `.doctor()`. Event append results include stable ID and sequence revision. Duplicate IDs with identical payloads are idempotent; different payloads fail. Batch writes are transactional. SQLite serializes concurrent writers. A content chain detects accidental history changes, not malicious authenticated authorship.

Capture adapters expose `normalize(payload, root, owned_paths=()) -> list[dict]` and need no sibling skill. Hooks record supported events only. `source_event_id` groups deliveries; receipt IDs hash distinct bounded/redacted observations, so identical retries are idempotent while changed facts or running-to-completed observations are retained without automatic supersession. Stop events without reliable identity use UUIDs with limited deduplication. Relative file references resolve against hook `cwd`, with explicit fallback or omission metadata. Coverage boundaries and errors remain explicit. Skill-only use supports deliberate checkpoints; hook configuration is generated for review and never installed silently.

Research-driven acceptance: transitive corrections; stale dependencies; authority conflicts; full-packet overflow with Unicode; exact file evidence; failed versus running checks; multiple stops; retry delivery; same wording with changed facts; capture errors; scope isolation; safe rendering; atomic projection revisions; unknown events; standalone installation.

Release claims must distinguish deterministic fixture tests, agent skill-use trials, and native host/provider tests. No claim of global novelty or measured token savings without a comparative benchmark.

Measured manual skill-use trials with 1,000-byte briefs required overflow retrieval. Multi-ID `get` reduces repeated retrieval calls but does not establish net efficiency or superior task outcomes.
