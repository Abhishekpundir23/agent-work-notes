# Claude Code capture

Deliberate checkpoint recording works without hooks. Optional hooks add receipts for supported host events; they cannot observe all activity or infer the reasons for an action.

Print configuration for the specific project root and task:

```sh
python3 /absolute/path/to/claude-work-notes/scripts/notes.py --root /absolute/project --task retry-timeouts hook-config
```

Review its commands and merge its event groups into the project's `.claude/settings.json`, preserving existing settings and hooks. Do not replace unrelated configuration or silently modify global settings. The task argument in a generated command remains fixed: generate and select configuration for the intended task before capture. This skill does not install hooks through frontmatter.

Use `/hooks` to inspect configured handlers. Report configuration generated, configuration merged, and observed capture separately. Merely loading the skill or finding a settings file does not establish capture.

The adapter follows [official Claude Code hooks documentation](https://code.claude.com/docs/en/hooks), reviewed 2026-10-15:

- `PostToolUse` and `PostToolUseFailure` have different payloads. Preserve failure information without assuming it appears in `tool_response`.
- Stop marks a response boundary. Session-only identities cannot distinguish repeated responses. Prefer supplied identity fields and avoid treating replay as new work.
- Transcript writes can lag; the supplied final message is more appropriate at Stop than assuming the latest transcript line is current.
- Validation failures, permission decisions, cancellations, and API failures have different event coverage. Hooks do not guarantee an exhaustive history.

Keep initial capture time and coverage gaps explicit. Run a native Claude Code trial covering failed tools, multiple responses, and compaction recovery before describing that installation as verified. Current documentation can exceed the feature set of an older installed CLI; retain unsupported events as unknown and inspect the actual host version.

For script paths in skill content, `${CLAUDE_SKILL_DIR}` is documented by the [skills reference](https://code.claude.com/docs/en/skills). Do not assume that variable is substituted inside hook commands. Use the configuration generator's resolved paths.

## Receipt identity and file scope

`source_event_id` groups deliveries from one source event. The receipt ID also hashes the bounded, redacted observation: identical retry deliveries are idempotent, while changed captured facts or a running-to-completed update produce separate receipts. They do not automatically supersede earlier observations. Differences removed by truncation or redaction are outside that distinction; inspect capture metadata and retain useful missing evidence deliberately.

A Stop event without reliable identity receives a UUID, so retry deduplication is limited in that case. This preserves potentially distinct responses rather than silently collapsing them.

Relative file references resolve against the hook payload’s working directory and are then checked against the explicit project root. If `cwd` is absent, the configured root is used and marked; an invalid supplied `cwd` prevents ambiguous relative references from being recorded. File presence and hashes remain limited evidence.
