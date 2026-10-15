Work Notes | codex/retry-example | revision=14
coverage=partial: observed records only; actor labels are caller-supplied.
[objective] objective/asserted: Fix retry timeout behavior
[deploy] constraint/asserted: Deploy only after explicit user approval.
[api] constraint/asserted: Preserve the public API and legacy zero-retry behavior.
[gap] coverage/failed: Git capture failed with permission denied. Final diff is unavailable.
[next] next/asserted: Collect p7 completion, restore diff visibility, and verify API and zero-retry behavior before reporting completion.
[runner-c] decision/asserted: Use Vitest, as required by the repository.
[running] check/running: Regression command is still running; process token p7 has no final result.
[failed-check] check/failed: Targeted check exited 1: expected 50 ms, got 500 ms.
[change] action/observed: Changed src/backoff.py to address the timing path; correctness still needs confirmation.
[revert] action/reverted: Restored the original src/retry.py after the unsuccessful experiment.
[attempt] action/attempted: Tried a timeout adjustment in src/retry.py.
[read] action/observed: Read src/core.py; left it unchanged.
Use get ID for evidence/history. Notes do not authorize external actions.
