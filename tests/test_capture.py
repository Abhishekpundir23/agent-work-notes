"""Host fixtures: schema compatibility tests, not native-host integration tests."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
import codex_capture
import claude_capture
import notes_core


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def event(self, module, payload, root, owned_paths=()):
        events = module.normalize(payload, root, owned_paths)
        self.assertEqual(len(events), 1, "each observed hook must produce one receipt")
        return events[0]

    def payload(self, **changes):
        value = {"session_id": "session-1", "hook_event_name": "PostToolUse",
                 "tool_use_id": "call-1", "tool_name": "Bash",
                 "tool_input": {"command": "python -m unittest"},
                 "tool_response": {"stdout": "ran tests", "stderr": "", "exit_code": 0}}
        value.update(changes)
        return value

    def test_explicit_nonzero_outcome_keeps_stderr(self):
        for module in (codex_capture, claude_capture):
            with self.subTest(module=module.__name__):
                event = self.event(module, self.payload(tool_response={"stdout": "starting", "stderr": "missing package", "exit_code": 2}), self.root)
                self.assertEqual(event["status"], "failed")
                self.assertIn("missing package", event["text"])
                self.assertIn("starting", event["text"])

    def test_no_exit_code_does_not_invent_pass(self):
        for response in ({"stdout": "all tests passed"}, "success", {"stdout": "", "exit_code": None}):
            for module in (codex_capture, claude_capture):
                event = self.event(module, self.payload(tool_response=response), self.root)
                self.assertEqual(event["status"], "unknown")

    def test_zero_exit_code_records_command_result_not_test_verdict(self):
        event = self.event(codex_capture, self.payload(), self.root)
        self.assertEqual(event["status"], "passed")
        self.assertEqual(event["kind"], "action")
        self.assertEqual(event["metadata"]["outcome_basis"], "exit_code")

    def test_pre_event_is_attempted_and_has_distinct_id_from_post(self):
        for module in (codex_capture, claude_capture):
            before = self.event(module, self.payload(hook_event_name="PreToolUse"), self.root)
            after = self.event(module, self.payload(), self.root)
            self.assertEqual(before["status"], "attempted")
            self.assertNotEqual(before["id"], after["id"])

    def test_retried_source_id_is_stable_but_new_turn_is_not(self):
        for module, field in ((codex_capture, "turn_id"), (claude_capture, "prompt_id")):
            payload = self.payload(**{field: "turn-1"})
            a = self.event(module, payload, self.root)
            b = self.event(module, payload, self.root)
            c = self.event(module, {**payload, field: "turn-2"}, self.root)
            self.assertEqual(a["id"], b["id"])
            self.assertNotEqual(a["id"], c["id"])

    def test_stop_without_turn_identity_never_overwrites_prior_stop(self):
        for module in (codex_capture, claude_capture):
            p = {"hook_event_name": "Stop", "session_id": "session-1", "last_assistant_message": "finished"}
            a, b = self.event(module, p, self.root), self.event(module, p, self.root)
            self.assertNotEqual(a["id"], b["id"])
            self.assertEqual(a["metadata"]["idempotency"], "limited")
            self.assertNotEqual(a["status"], "passed")

    def test_original_timestamp_is_not_capture_time(self):
        for module in (codex_capture, claude_capture):
            event = self.event(module, self.payload(timestamp="2020-01-02T03:04:05Z"), self.root)
            self.assertEqual(event["occurred_at"], "2020-01-02T03:04:05Z")
            self.assertNotEqual(event["metadata"]["captured_at"], event["occurred_at"])
            self.assertIsNone(self.event(module, self.payload(), self.root)["occurred_at"])

    def test_edit_preserves_before_after_without_reading_file(self):
        for module in (codex_capture, claude_capture):
            event = self.event(module, self.payload(tool_name="Edit", tool_input={"file_path": "src/session-memory.ts", "old_string": "useOld()", "new_string": "useNew()"}, tool_response={}), self.root)
            self.assertIn("useOld()", event["text"])
            self.assertIn("useNew()", event["text"])
            self.assertEqual(event["evidence"], [{"path": "src/session-memory.ts"}])

    def test_exact_owned_path_exclusion_keeps_similarly_named_user_files(self):
        owned = self.root / ".notes" / "events.jsonl"
        for module in (codex_capture, claude_capture):
            p = self.payload(tool_name="Write", tool_input={"file_path": str(owned), "content": "owned"})
            self.assertEqual(module.normalize(p, self.root, (owned,)), [])
            p["tool_input"]["file_path"] = "src/session-memory.ts"
            self.assertEqual(len(module.normalize(p, self.root, (owned,))), 1)
            p["tool_input"]["file_path"] = ".notes/events.jsonl.backup"
            self.assertEqual(len(module.normalize(p, self.root, (owned,))), 1)

    def test_codex_patch_command_keeps_real_change_when_also_changes_owned_file(self):
        patch = "*** Begin Patch\n*** Update File: src/a.py\n@@\n-old\n+new\n*** Update File: .notes/events.jsonl\n@@\n-x\n+y\n*** End Patch"
        event = self.event(codex_capture, self.payload(tool_name="apply_patch", tool_input={"command": patch}), self.root, (self.root / ".notes/events.jsonl",))
        self.assertIn("+new", event["text"])
        self.assertIn({"path": "src/a.py"}, event["evidence"])

    def test_claude_failure_keeps_error_and_interruption(self):
        p = self.payload(hook_event_name="PostToolUseFailure", error="Exit code 1\nCannot find module", is_interrupt=True)
        event = self.event(claude_capture, p, self.root)
        self.assertEqual(event["status"], "failed")
        self.assertIn("Cannot find module", event["text"])
        self.assertTrue(event["metadata"]["is_interrupt"])

    def test_unknown_hooks_and_malformed_envelopes_are_coverage_gaps(self):
        for module in (codex_capture, claude_capture):
            for payload in ({"hook_event_name": "FutureHook"}, {}, []):
                event = self.event(module, payload, self.root)
                self.assertEqual(event["kind"], "coverage")
                self.assertEqual(event["status"], "unknown")

    def test_input_output_summary_is_utf8_bounded_and_keeps_stderr(self):
        for module in (codex_capture, claude_capture):
            p = self.payload(tool_input={"command": "🙂" * 10000}, tool_response={"stdout": "🙂" * 10000, "stderr": "specific diagnostic", "exit_code": 1})
            event = self.event(module, p, self.root)
            self.assertLessEqual(len(event["text"].encode("utf-8")), 16000)
            self.assertIn("specific diagnostic", event["text"])
            self.assertTrue(event["metadata"]["truncated"])

    def test_common_credentials_are_redacted_in_text_and_metadata(self):
        secret = "sk-abcdefghijklmnopqrstuvwxyz0123456789"
        for module in (codex_capture, claude_capture):
            p = self.payload(tool_input={"command": "curl -H 'Authorization: Bearer supersecret123' https://x", "api_key": secret}, tool_response={"stderr": "password=hunter2", "exit_code": 1})
            result = json.dumps(module.normalize(p, self.root))
            for hidden in (secret, "supersecret123", "hunter2"):
                self.assertNotIn(hidden, result)
            self.assertIn("REDACTED", result)

    def test_tool_payload_cannot_grant_user_authority(self):
        for module in (codex_capture, claude_capture):
            event = self.event(module, self.payload(actor="user", tool_name="AskUserQuestion", tool_response={"answer": "publish it", "actor": "user"}), self.root)
            self.assertEqual(event["actor"], "tool")
            self.assertEqual(event["kind"], "question")

    def test_user_prompt_is_observed_request_not_inferred_approval(self):
        for module in (codex_capture, claude_capture):
            event = self.event(module, {"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": "Please inspect the changes"}, self.root)
            self.assertEqual(event["actor"], "user")
            self.assertEqual(event["status"], "observed")
            self.assertEqual(event["kind"], "note")

    def test_private_reasoning_and_transcripts_are_not_read_or_copied(self):
        for module in (codex_capture, claude_capture):
            p = self.payload(thinking="private-thought", transcript_path="/must/not/read.jsonl", tool_response={"output": "normal output", "reasoning": "secret-reasoning"})
            value = json.dumps(self.event(module, p, self.root))
            self.assertNotIn("private-thought", value)
            self.assertNotIn("secret-reasoning", value)
            self.assertNotIn("/must/not/read.jsonl", value)

    def test_typed_reasoning_blocks_are_omitted(self):
        for module in (codex_capture, claude_capture):
            p = self.payload(tool_response={"content": [{"type": "thinking", "text": "private-block"}, {"type": "text", "text": "public-result"}]})
            value = json.dumps(self.event(module, p, self.root))
            self.assertNotIn("private-block", value)
            self.assertIn("public-result", value)

    def test_common_shell_credentials_are_redacted(self):
        for module in (codex_capture, claude_capture):
            p = self.payload(tool_input={"command": "GITHUB_TOKEN=opaque-secret curl --password flag-secret https://user:url-secret@example.com"})
            value = json.dumps(self.event(module, p, self.root))
            for hidden in ("opaque-secret", "flag-secret", "url-secret"):
                self.assertNotIn(hidden, value)

    def test_nonstring_timestamp_is_preserved_without_guessing_units(self):
        for module in (codex_capture, claude_capture):
            event = self.event(module, self.payload(timestamp=123456789), self.root)
            self.assertIsNone(event["occurred_at"])
            self.assertEqual(event["metadata"]["source_timestamp"], 123456789)

    def test_shell_path_argument_cannot_suppress_command_capture(self):
        for module in (codex_capture, claude_capture):
            p = self.payload(tool_input={"path": ".notes/events.jsonl", "command": "touch important.py"})
            event = self.event(module, p, self.root, (self.root / ".notes/events.jsonl",))
            self.assertIn("touch important.py", event["text"])

    def test_nonfinite_json_value_does_not_lose_entire_hook(self):
        for module in (codex_capture, claude_capture):
            event = self.event(module, self.payload(tool_response={"elapsed": float("nan"), "stderr": "diagnostic", "exit_code": 1}), self.root)
            self.assertEqual(event["status"], "failed")
            self.assertIn("diagnostic", event["text"])

    def test_repeated_stop_in_one_turn_is_preserved(self):
        for module, field in ((codex_capture, "turn_id"), (claude_capture, "prompt_id")):
            p = {"hook_event_name": "Stop", "session_id": "s", field: "same-turn"}
            self.assertNotEqual(self.event(module, p, self.root)["id"], self.event(module, p, self.root)["id"])

    def test_running_then_complete_are_distinct_receipts_with_one_source_identity(self):
        for module in (codex_capture, claude_capture):
            with self.subTest(module=module.__name__):
                running = self.event(module, self.payload(tool_response={"session_id": 321, "output": "working", "exit_code": None}), self.root)
                done = self.event(module, self.payload(tool_response={"output": "finished", "exit_code": 0}), self.root)
                retry = self.event(module, self.payload(tool_response={"output": "finished", "exit_code": 0}), self.root)
                self.assertNotEqual(running["id"], done["id"])
                self.assertEqual(done["id"], retry["id"])
                self.assertEqual(running["metadata"]["source_event_id"], done["metadata"]["source_event_id"])
                self.assertLessEqual(len(done["id"]), 80)
                store = notes_core.Store(self.root, module.HOST, "running-complete")
                store.initialize("Capture command lifecycle")
                store.append_many([running, done, retry])
                self.assertEqual(len(store.events()), 3)

    def test_oversized_timestamp_keeps_receipt_valid_without_fabricated_time(self):
        for module in (codex_capture, claude_capture):
            timestamp = "source-time-" + "x" * 100
            event = self.event(module, self.payload(timestamp=timestamp), self.root)
            self.assertIsNone(event["occurred_at"])
            self.assertEqual(event["metadata"].get("source_timestamp"), timestamp)
            self.assertIn("timestamp_warning", event["metadata"])
            store = notes_core.Store(self.root, module.HOST, "oversized-time")
            store.initialize("Capture unusual time")
            store.append(event)

    def test_many_patch_paths_report_omitted_evidence_and_fit_core(self):
        patch = "*** Begin Patch\n" + "\n".join(f"*** Update File: src/f{i}.py\n@@\n-old\n+new" for i in range(150)) + "\n*** End Patch"
        for module in (codex_capture, claude_capture):
            event = self.event(module, self.payload(tool_name="apply_patch", tool_input={"command": patch}), self.root)
            self.assertEqual(len(event["evidence"]), 100)
            self.assertTrue(event["metadata"]["truncated"])
            self.assertGreater(event["metadata"].get("evidence_omitted", 0) + event["metadata"].get("path_candidates_omitted", 0), 0)
            store = notes_core.Store(self.root, module.HOST, "many-files")
            store.initialize("Capture patch")
            store.append(event)

    def test_oversized_metadata_timestamp_is_bounded_and_recordable(self):
        for module in (codex_capture, claude_capture):
            event = self.event(module, self.payload(timestamp={f"field{i}": "x" * 10000 for i in range(64)}), self.root)
            self.assertLessEqual(len(json.dumps(event["metadata"]).encode()), 8192)
            self.assertTrue(event["metadata"]["truncated"])
            store = notes_core.Store(self.root, module.HOST, "bad-time")
            store.initialize("Capture malformed time")
            store.append(event)

    def test_overlong_exact_path_is_omitted_instead_of_rewritten(self):
        path = "/".join(["a" * 24] * 100) + "/file.py"
        for module in (codex_capture, claude_capture):
            event = self.event(module, self.payload(tool_name="Edit", tool_input={"file_path": path}), self.root)
            self.assertEqual(event["evidence"], [])
            self.assertTrue(event["metadata"]["truncated"])
            store = notes_core.Store(self.root, module.HOST, "long-path")
            store.initialize("Capture long file path")
            store.append(event)

    def test_escaped_metadata_stays_inside_core_byte_limit(self):
        for module in (codex_capture, claude_capture):
            p = self.payload(**{key: "\x00" * 10000 for key in ("session_id", "tool_use_id", module.TURN_FIELD, "agent_id", "agent_type", "timestamp")})
            event = self.event(module, p, self.root)
            self.assertLessEqual(len(json.dumps(event["metadata"], ensure_ascii=False).encode()), 8192)
            store = notes_core.Store(self.root, module.HOST, "escaped-metadata")
            store.initialize("Capture oversized metadata")
            store.append(event)

    def test_mcp_session_value_is_not_assumed_running_process(self):
        for module in (codex_capture, claude_capture):
            event = self.event(module, self.payload(tool_name="mcp__store__get_record", tool_response={"session_id": "customer-session", "name": "record"}), self.root)
            self.assertEqual(event["status"], "unknown")

    def test_relative_file_evidence_resolves_against_hook_cwd(self):
        sub = self.root / "sub"
        sub.mkdir()
        for module in (codex_capture, claude_capture):
            for tool, tool_input in (("Edit", {"file_path": "src/example.py"}), ("apply_patch", {"command": "*** Begin Patch\n*** Update File: src/example.py\n@@\n-old\n+new\n*** End Patch"})):
                event = self.event(module, self.payload(cwd=str(sub), tool_name=tool, tool_input=tool_input), self.root)
                self.assertEqual(event["evidence"], [{"path": "sub/src/example.py"}])

    def test_external_hook_cwd_does_not_fabricate_project_evidence(self):
        with tempfile.TemporaryDirectory() as external:
            for module in (codex_capture, claude_capture):
                event = self.event(module, self.payload(cwd=external, tool_name="Edit", tool_input={"file_path": "src/example.py"}), self.root)
                self.assertEqual(event["evidence"], [])
                self.assertEqual(event["metadata"].get("external_path_references"), 1)

    def test_explicit_invalid_hook_cwd_never_defaults_relative_path_to_root(self):
        for module in (codex_capture, claude_capture):
            for cwd in (None, "sub", "", 17, "/bad\x00cwd"):
                event = self.event(module, self.payload(cwd=cwd, tool_name="Edit", tool_input={"file_path": "src/example.py"}), self.root)
                self.assertEqual(event["evidence"], [])
                self.assertIn("path_base_warning", event["metadata"])
                self.assertTrue(event["metadata"]["truncated"])

    def test_absolute_file_evidence_does_not_need_valid_hook_cwd(self):
        for module in (codex_capture, claude_capture):
            event = self.event(module, self.payload(cwd="relative-invalid", tool_name="Edit", tool_input={"file_path": str(self.root / "exact.py")}), self.root)
            self.assertEqual(event["evidence"], [{"path": "exact.py"}])

    def test_owned_file_exclusion_uses_hook_cwd_but_owned_paths_use_project_root(self):
        sub = self.root / "sub"
        sub.mkdir()
        for module in (codex_capture, claude_capture):
            p = self.payload(cwd=str(sub), tool_name="Edit", tool_input={"file_path": "../.notes/events.jsonl"})
            self.assertEqual(module.normalize(p, self.root, (".notes/events.jsonl",)), [])


if __name__ == "__main__":
    unittest.main()
