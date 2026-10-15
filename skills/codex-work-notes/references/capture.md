# Codex capture

Deliberate checkpoint recording works without hooks. Optional hooks add receipts for supported host events; they cannot observe all activity or infer the reasons for an action.

Print configuration for the specific project root and task:

```sh
python3 /absolute/path/to/codex-work-notes/scripts/notes.py --root /absolute/project --task retry-timeouts hook-config
```

Review its commands and merge its event groups into the project's `.codex/hooks.json`, preserving existing groups. Do not replace unrelated hooks or silently modify global settings. The task argument in a generated command remains fixed: generate and select configuration for the intended task before capture. Merely loading this skill does not install hooks.

Codex requires review and trust of non-managed hook definitions. Inspect them through `/hooks`; changed definitions can require review again. Report configuration generated, configuration merged, and observed capture separately. Never infer activation from the presence of a JSON file.

The adapter follows [official Codex hooks documentation](https://learn.chatgpt.com/docs/hooks), reviewed 2026-10-15:

- `PostToolUse` includes Bash commands that exited unsuccessfully. Tool outputs differ, so unrecognized results must remain unknown.
- `Bash` and `apply_patch` inputs use `tool_input.command`. A delayed command completion can arrive after `write_stdin` with the original call's identity.
- `SessionStart` with source `compact` is the context-restoration boundary. Restoring notes should respect the explicit root/task and the brief's overflow status.
- Hosted search and specialized tool paths can bypass local hooks. Transcript format is not a stable hook interface.

The generated configuration and adapter fixtures establish only the supported local behavior they exercise. A native Codex run must demonstrate capture and compaction recovery before describing that installation as verified. Record gaps when hooks are disabled, untrusted, unavailable, or started after work began. Manual checkpoints should retain important decisions or outcomes missing from capture.

## Receipt identity and file scope

`source_event_id` groups deliveries from one source event. The receipt ID also hashes the bounded, redacted observation: identical retry deliveries are idempotent, while changed captured facts or a running-to-completed update produce separate receipts. They do not automatically supersede earlier observations. Differences removed by truncation or redaction are outside that distinction; inspect capture metadata and retain useful missing evidence deliberately.

A Stop event without reliable identity receives a UUID, so retry deduplication is limited in that case. This preserves potentially distinct responses rather than silently collapsing them.

Relative file references resolve against the hook payload’s working directory and are then checked against the explicit project root. If `cwd` is absent, the configured root is used and marked; an invalid supplied `cwd` prevents ambiguous relative references from being recorded. File presence and hashes remain limited evidence.
