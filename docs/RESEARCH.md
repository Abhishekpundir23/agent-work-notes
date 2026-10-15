# Research basis and evaluation limits

Reviewed 2026-10-15. This project has two independent host skills. Its shared development code does not imply cross-agent collaboration.

The design goal is accurate, useful task continuation with visible capture limits. A structured record, decision map, brief, correction graph, or byte budget is not by itself novel. The contribution must be demonstrated through behavior and measured overhead.

## Audited failures that shaped the design

These findings concern the pinned versions below. They are not claims about every version or every operating mode of those projects.

| Project and revision | Observed failure or limitation | Design response |
| --- | --- | --- |
| Agent Flight Recorder, `5e9074804f1e9bd8a6e1c8cdcc579d34f4f3965b` | A corrupted Git index made Git capture fail while the recorder reported a clean result. [Error handling](https://github.com/gorillapioneer/agent-flight-recorder/blob/5e9074804f1e9bd8a6e1c8cdcc579d34f4f3965b/agent_flight_recorder/cli.py#L46-L49) | Keep capture failure distinct from no changes. |
| AgentMem, `c96ff3ce7a5286d33a7c280d53cafa1bfcb13693` | Basename matching accepted a claim about a nonexistent qualified path because a differently located file shared its name. [Receipt matching](https://github.com/AgentMem/agentmem/blob/c96ff3ce7a5286d33a7c280d53cafa1bfcb13693/packages/agentmem/src/agentmem/verify/receipt.py#L332-L340) | Preserve exact root-relative paths and the limited meaning of file evidence. |
| Deja, `291abcdf2ccbff1b84f2e76b2725d124a67d72ed` | Three-step correction could return an intermediate decision; an automatic handoff could retain an obsolete decision. [Recall path](https://github.com/acoyfellow/deja/blob/291abcdf2ccbff1b84f2e76b2725d124a67d72ed/src/index.ts#L191-L203) | Resolve correction chains and mark dependent records stale. |
| Deja, same revision | An oversized first note survived the requested token limit, with additional rendered material outside the calculation. [Budget handling](https://github.com/acoyfellow/deja/blob/291abcdf2ccbff1b84f2e76b2725d124a67d72ed/src/index.ts#L752-L764) | Bound complete output and make overflow recoverable. |
| claude-mem, `fef3402e674bebbf72a23aeb735e91c92cd34afd` | Equal titles and narratives caused an updated observation with changed facts to be discarded by observation deduplication. The raw tool index could still retain evidence. [Hash inputs](https://github.com/thedotmack/claude-mem/blob/fef3402e674bebbf72a23aeb735e91c92cd34afd/src/services/sqlite/observations/store.ts#L16-L24) | Deduplicate identical delivery, not meaningful changes with similar summaries. |

AFR probes used its CLI in disposable checkouts. Other reproductions used unchanged functions with bounded compatibility harnesses or extracted source-level functions; they were not native live Claude/Bun integration trials. Counterevidence matters: AFR preserves before/after commit IDs; AgentMem snapshots existing dirty file content; Deja documents budget limitations; claude-mem retains other capture layers. A failing case does not erase those capabilities.

The earlier audit also found existing solutions. [Agent Memory System budgets complete rendered context](https://github.com/rrrrrredy/agent-memory-system/blob/dc53ddb98b9eeb29ca0e7aad57841d53e126ff9c/internal/retrieval/context.go#L62-L95); [Selvedge records decision reasons and rejected alternatives](https://github.com/masondelan/selvedge). Neither capability should be presented as our invention.

## Host contracts

[Codex hooks](https://learn.chatgpt.com/docs/hooks) document local tool payloads, nonzero Bash results in `PostToolUse`, optional transcript availability, and post-compaction restoration through `SessionStart`. Hosted search and some specialized tool paths bypass hooks. Non-managed hooks require trust review.

[Claude Code hooks](https://code.claude.com/docs/en/hooks) distinguish successful and failed tool payloads, expose response-level Stop events, and describe gaps around validation, interruption, and failure. Transcript writing can lag hook execution. The adapter must not treat either host's event stream as an exhaustive audit trail.

Read-only local version checks found Codex `0.162.0-alpha.17.2` and Claude Code `2.1.277`. They establish installed versions, not native capture behavior. Current documentation may describe capabilities beyond an older installed release. Fixture conformance, configured hooks, and observed native events remain separate claims.

## Three research lessons

### Measure the net effect of notes

[Evaluating AGENTS.md, revision 3](https://arxiv.org/abs/2602.11988v3) reports no general success improvement and higher average inference cost in its tested settings. [On the Impact of AGENTS.md, revision 2](https://arxiv.org/abs/2601.20404v2) reports reduced median runtime and output tokens in a different 124-PR study. These experiments differ and do not evaluate this notes system.

Implication: compare task success and constraint adherence alongside total input/output tokens, note-maintenance calls, capture/render latency, and repeated investigations. A smaller brief alone is not an efficiency result. Count failed and neutral trials, and publish results separately for each host.

### Test updates and the ability to say unknown

[LongMemEval](https://arxiv.org/abs/2410.10813v2) evaluates extraction, reasoning over sessions and time, knowledge updates, and abstention. It separates indexing, retrieval, and reading. Its conversation-memory results are not evidence of coding task success.

Implication: include absent evidence, conflicting evidence, multi-step corrections, delayed ingestion, and time-scoped queries. Measure whether an agent follows recovered constraints as well as whether a search finds them. A later inference cannot overwrite a user requirement merely because it is newer.

### Test important facts in inconvenient positions

[Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/) found position-dependent performance on long-context question answering and key-value retrieval with the models tested. This older result does not establish the size of the effect in current Codex or Claude models.

Implication: keep current objectives, applicable constraints, and unresolved conflicts prominent. Include long histories where a still-binding constraint appears between many unrelated successful actions. Treat the chosen ordering as a hypothesis until a host-specific continuation trial tests it.

## Evaluation contract

The deterministic regression suite should establish software invariants: transactional batches, concurrent capture, exact-path evidence, same-ID conflict detection, transitive corrections and staleness, authority restrictions, overflow, safe rendering, scope isolation, and standalone packaging.

Independent skill-use exercises should test realistic decisions: recover the correct task, preserve a failed check, retrieve omitted constraints, and recognize that a new user instruction changes the current brief. The preliminary control exercise produced a 939-byte brief that retained its supplied constraints, pending check, and capture error without this skill. That successful baseline is useful evidence; it does not demonstrate a baseline failure or our superiority.

Manual skill-use trials with 1,000-byte briefs needed overflow retrieval. The interface now supports fetching up to 100 exact IDs together, reducing the mechanics of repeated lookups; it does not establish lower total token cost or better task success. The trials also exposed duplicated restrictions in objectives, so the skill now separates a short goal from constraint records.

Native host trials must separately exercise startup, delayed completion, tool failure, repeated response endings, disabled capture, and compaction recovery. Record host/model version and actual coverage. No authenticated native host trial is established by the research pass.

For comparative trials, hold initial repository state, task, available instructions, and interruption boundary constant. Compare native continuation, ordinary short notes, and the skill. Publish raw outcomes and costs rather than only aggregate savings. No claimed percentage improvement, universal completeness, or global novelty is supported before those trials.

## Bounded research backlog

- Check host schema changes before adapting capture; add fixtures for demonstrated changes.
- Investigate whether immutable generated views reduce stale-brief mistakes in real continuation tasks.
- Measure checkpoint frequency and retrieval thresholds instead of adding features by intuition.
- Test whether timestamps and dependency links provide enough useful retrieval without embeddings or a model summarizer.
- Keep all changes tied to a reproducible failure or a measurable improvement hypothesis.
