"""Normalize Claude Code hook envelopes without a model or transcript access.

Schema reference: https://code.claude.com/docs/en/hooks (reviewed 2026-10-15).
This is bounded, best-effort capture of delivered hooks, not complete activity
capture or proof of user authorization. Redaction covers common credential
shapes; unknown secrets and sensitive prose require caller policy/review.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import uuid

HOST = "claude"
TURN_FIELD = "prompt_id"
TOOL_EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure"}
LIFECYCLE = {"SessionStart", "SessionEnd", "PreCompact", "PostCompact", "Stop", "StopFailure", "SubagentStart", "SubagentStop", "PermissionDenied"}
_SECRET_KEY = re.compile(r"(?i)(?:^|[_-])(?:password|passwd|secret|token|api[_-]?key|authorization|cookie|credential|private[_-]?key)(?:$|[_-])")
_PRIVATE_KEYS = {"thinking", "reasoning", "chain_of_thought", "analysis", "transcript", "transcript_path"}


def _clip(text, limit, flags):
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= limit:
        return text
    flags["truncated"] = True
    suffix = " [truncated]"
    return raw[:max(0, limit-len(suffix))].decode("utf-8", errors="ignore") + suffix


def _redact(text, flags):
    original = text
    text = re.sub(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----.*?(?:-----END (?:[A-Z ]+ )?PRIVATE KEY-----|$)", "[REDACTED PRIVATE KEY]", text, flags=re.S)
    text = re.sub(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+", r"\1 [REDACTED]", text)
    text = re.sub(r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{16,}|github_pat_[A-Za-z0-9_]{16,}|AKIA[A-Z0-9]{16})\b", "[REDACTED]", text)
    text = re.sub(r"(?i)(\b(?:password|passwd|secret|token|api[_-]?key|access[_-]?key|authorization)\b\s*[=:]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;\}\]]+)", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(\b[A-Z_]*(?:TOKEN|PASSWORD|SECRET|API_KEY|ACCESS_KEY)[A-Z_]*\s*=\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(--(?:password|passwd|token|secret|api-key)\s+)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(https?://)[^/\s:@]+:[^/\s@]+@", r"\1[REDACTED]@", text)
    if text != original:
        flags["redacted"] = True
    return text


def _safe(value, flags, depth=0):
    if depth > 8:
        flags["truncated"] = True
        return "[nested content omitted]"
    if isinstance(value, dict):
        if value.get("type") in ("thinking", "reasoning", "redacted_thinking"):
            return "[private reasoning omitted]"
        clean = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 64:
                flags["truncated"] = True
                clean["_omitted"] = "remaining fields"
                break
            key = str(key)
            if key.lower() in _PRIVATE_KEYS:
                continue
            safe_key = _clip(_redact(key, flags), 256, flags)
            if _SECRET_KEY.search(key):
                clean[safe_key] = "[REDACTED]"
                flags["redacted"] = True
            else:
                clean[safe_key] = _safe(item, flags, depth+1)
        return clean
    if isinstance(value, list):
        if len(value) > 32:
            flags["truncated"] = True
        return [_safe(item, flags, depth+1) for item in value[:32]]
    if isinstance(value, str):
        return _clip(_redact(value, flags), 6000, flags)
    if isinstance(value, float) and not math.isfinite(value):
        flags["truncated"] = True
        return "[nonfinite number omitted]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return "[unsupported value]"


def _summary(value, limit, flags):
    clean = _safe(value, flags)
    rendered = clean if isinstance(clean, str) else json.dumps(clean, ensure_ascii=False, sort_keys=True, allow_nan=False)
    return _clip(rendered, limit, flags)


def _bound_metadata(metadata):
    # JSON escaping can multiply a short source string's size. Budget the
    # actual stored representation, including source identity and timestamps.
    while len(json.dumps(metadata, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()) > 8192:
        strings = [(len(json.dumps(value, ensure_ascii=False).encode()), key)
                   for key, value in metadata.items() if isinstance(value, str) and len(value.encode()) > 80]
        if not strings:
            # The only non-string source value is an unusual numeric timestamp.
            metadata["source_timestamp"] = "[oversized timestamp omitted]"
            metadata["truncated"] = True
            break
        _, key = max(strings)
        metadata[key] = _clip(metadata[key], max(64, len(metadata[key].encode()) // 2), metadata)


def _canonical(path, root):
    candidate = Path(path)
    if not candidate.is_absolute():
        if root is None:
            raise ValueError("Relative file reference has no valid hook cwd")
        candidate = root / candidate
    return candidate.resolve()


def _hook_cwd(payload, root, flags):
    if "cwd" not in payload:
        flags["path_base"] = "configured_root_no_hook_cwd"
        return root
    cwd = payload["cwd"]
    if isinstance(cwd, str) and cwd and "\x00" not in cwd:
        try:
            candidate = Path(cwd)
            if candidate.is_absolute():
                candidate = candidate.resolve()
                # A delayed event may name a directory that no longer exists.
                # Its absolute source path is still usable as a reference base;
                # an existing nondirectory is not a valid working directory.
                if not candidate.exists() or candidate.is_dir():
                    flags["path_base"] = "hook_cwd"
                    flags["cwd"] = _clip(_redact(str(candidate), flags), 512, flags)
                    return candidate
        except (ValueError, OSError, RuntimeError):
            pass
    flags["truncated"] = True
    flags["path_base_warning"] = "invalid_hook_cwd_relative_references_omitted"
    return None


def _paths(tool_input, root, flags):
    paths = []
    if isinstance(tool_input, dict):
        for key in ("file_path", "path"):
            if isinstance(tool_input.get(key), str) and tool_input[key]:
                paths.append(tool_input[key])
        patch = tool_input.get("command")
        if isinstance(patch, str) and patch.startswith("*** Begin Patch"):
            paths.extend(re.findall(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$", patch, re.M))
    result = []
    if len(paths) > 128:
        flags["truncated"] = True
        flags["path_candidates_omitted"] = len(paths) - 128
    for path in paths[:128]:
        try:
            resolved = _canonical(path, root)
        except (ValueError, OSError, RuntimeError):
            flags["truncated"] = True
            flags["path_resolution_failures"] = flags.get("path_resolution_failures", 0) + 1
            continue
        if resolved not in result:
            result.append(resolved)
    return result


def _event_id(payload, event_name, metadata):
    session = payload.get("session_id")
    call = payload.get("tool_use_id")
    turn = payload.get(TURN_FIELD)
    explicit = payload.get("event_id")
    reliable = None
    if isinstance(session, str) and session:
        if event_name in TOOL_EVENTS and isinstance(call, str) and call:
            reliable = [HOST, session, event_name, call, turn]
        elif event_name == "UserPromptSubmit" and isinstance(turn, str) and turn:
            reliable = [HOST, session, event_name, turn]
        elif isinstance(explicit, str) and explicit:
            reliable = [HOST, session, event_name, explicit]
    if reliable is None:
        metadata["idempotency"] = "limited"
        return str(uuid.uuid4())
    metadata["idempotency"] = "source_identity"
    return HOST + "-" + hashlib.sha256(json.dumps(reliable, sort_keys=True).encode()).hexdigest()


def _outcome(payload, event_name):
    if event_name == "PreToolUse":
        return "attempted", "pre_execution"
    if event_name == "PostToolUseFailure":
        return "failed", "failure_hook"
    response = payload.get("tool_response")
    if isinstance(response, dict):
        if response.get("isError") is True or response.get("is_error") is True:
            return "failed", "explicit_error"
        for key in ("exit_code", "exitCode"):
            code = response.get(key)
            if isinstance(code, int) and not isinstance(code, bool):
                return ("passed" if code == 0 else "failed"), "exit_code"
        if payload.get("tool_name") in ("Bash", "PowerShell", "exec_command", "shell") and response.get("session_id") is not None and response.get("exit_code") is None:
            return "running", "process_session"
    return "unknown", "no_structured_outcome"


def normalize(payload: dict, root: Path, owned_paths: tuple = ()) -> list[dict]:
    """Return bounded receipts. Never read a transcript or infer authorization.

    The caller validates storage/task scope. File evidence names are exact
    project-relative references only, without a claim that a file was read or
    modified. Tool payloads remain untrusted data. Occurrence time is absent
    unless the envelope supplied a string timestamp; capture time is separate.
    """
    root = Path(root).resolve()
    flags = {"redacted": False, "truncated": False}
    malformed = not isinstance(payload, dict)
    payload = payload if isinstance(payload, dict) else {}
    event_name = payload.get("hook_event_name")
    if not isinstance(event_name, str):
        event_name = "unknown"
    metadata = {"host": HOST, "hook_event_name": _clip(_redact(event_name, flags), 128, flags),
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "coverage": "delivered_hooks_only"}
    for key in ("session_id", "tool_use_id", TURN_FIELD, "agent_id", "agent_type"):
        if isinstance(payload.get(key), str):
            metadata[key] = _clip(_redact(payload[key], flags), 256, flags)
    timestamp = payload.get("occurred_at", payload.get("timestamp"))
    occurred_at = None
    if isinstance(timestamp, str) and len(timestamp) <= 80:
        occurred_at = _redact(timestamp, flags)
        if len(occurred_at) > 80:
            occurred_at = None
    if timestamp is not None and occurred_at is None:
        metadata["timestamp_warning"] = "unsupported or oversized source timestamp; occurrence time unavailable"
        if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
            metadata["source_timestamp"] = _safe(timestamp, flags)
        else:
            metadata["source_timestamp"] = _summary(timestamp, 512, flags)
        if isinstance(timestamp, str) and len(timestamp) > 80:
            flags["truncated"] = True
    ident = _event_id(payload, event_name, metadata)
    evidence = []
    actor, kind, status = "system", "coverage", "unknown"
    text = "Unrecognized hook; activity coverage is unknown."
    if malformed:
        text = "Malformed hook envelope; activity coverage is unknown."
    elif event_name in TOOL_EVENTS and isinstance(payload.get("tool_name"), str):
        actor, kind = "tool", "action"
        tool = _clip(_redact(payload["tool_name"], flags), 256, flags)
        if tool in ("AskUserQuestion", "request_user_input", "request_user_input_async"):
            kind = "question"
        tool_input = payload.get("tool_input")
        path_base = _hook_cwd(payload, root, flags)
        paths = [] if tool in ("Bash", "PowerShell", "exec_command", "shell") else _paths(tool_input, path_base, flags)
        owned = set()
        for path in owned_paths:
            try:
                owned.add(_canonical(path, root))
            except (ValueError, OSError, RuntimeError):
                continue
        if paths and not flags.get("path_candidates_omitted") and not flags.get("path_resolution_failures") and all(path in owned for path in paths):
            return []
        for path in paths:
            if path in owned:
                continue
            try:
                relative = path.relative_to(root).as_posix()
            except ValueError:
                metadata["external_path_references"] = metadata.get("external_path_references", 0) + 1
                continue
            redacted_path = _redact(relative, flags)
            if redacted_path != relative:
                metadata["sensitive_path_references_omitted"] = True
                continue
            if len(relative) > 2048 or len(evidence) >= 100:
                metadata["evidence_omitted"] = metadata.get("evidence_omitted", 0) + 1
                flags["truncated"] = True
                continue
            evidence.append({"path": relative})
        status, metadata["outcome_basis"] = _outcome(payload, event_name)
        parts = [f"{event_name}: {tool}", "input: " + _summary(tool_input, 5200, flags)]
        response = payload.get("tool_response")
        if event_name != "PreToolUse":
            # Reserve space for diagnostics even when stdout is enormous.
            if isinstance(response, dict) and "stderr" in response:
                parts.append("stderr: " + _summary(response["stderr"], 3000, flags))
                response = {key: value for key, value in response.items() if key != "stderr"}
            parts.append("response: " + _summary(response, 5200, flags))
            if "error" in payload:
                parts.append("error: " + _summary(payload["error"], 1800, flags))
            if isinstance(payload.get("is_interrupt"), bool):
                metadata["is_interrupt"] = payload["is_interrupt"]
        text = "\n".join(parts)
    elif event_name == "UserPromptSubmit":
        actor, kind, status = "user", "note", "observed"
        text = "User prompt observed: " + _summary(payload.get("prompt", "[prompt absent]"), 12000, flags)
        metadata["authority"] = "source_prompt_only_no_inferred_approval"
    elif event_name in LIFECYCLE:
        kind, status = "coverage", "observed"
        data = {key: payload[key] for key in ("source", "trigger", "reason", "stop_hook_active", "is_interrupt") if key in payload}
        text = event_name + ": " + _summary(data, 2000, flags) + "; this lifecycle receipt does not establish task completion."
        if event_name == "SessionStart":
            metadata["coverage_limit"] = 'Some validation rejections and cancellations do not emit tool hooks; Stop is per response, not proof of task completion.'
        if event_name in ("Interrupt", "StopFailure"):
            status = "unknown"
            text += " Work may be incomplete."
    text = _clip(text, 16000, flags)
    metadata.update(flags)
    event = {"id": ident, "kind": kind, "text": text, "actor": actor,
             "status": status, "source": HOST + ":hook:" + metadata["hook_event_name"],
             "occurred_at": occurred_at, "evidence": evidence,
             "depends_on": [], "supersedes": [], "metadata": metadata}
    if metadata["idempotency"] == "source_identity":
        # A host call can deliver progress followed by completion. Group by
        # source identity while preserving each distinct captured observation.
        # No implied supersession: completion may arrive alone or out of order.
        metadata["source_event_id"] = ident
        metadata["idempotency"] = "source_identity_and_observation"
        _bound_metadata(metadata)
        semantic = {**event, "metadata": {key: value for key, value in metadata.items() if key != "captured_at"}}
        digest = hashlib.sha256(json.dumps(semantic, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()
        event["id"] = HOST + "-" + digest
    else:
        _bound_metadata(metadata)
    return [event]
