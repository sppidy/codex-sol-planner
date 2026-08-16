# Codex Sol Planner

`codex-sol-planner` provides the `$sol-plan-implement` workflow:

1. GPT-5.6 Sol at `xhigh` inspects the project and writes an identified,
   testable implementation plan.
2. Codex asks you to approve that exact plan by default.
3. The approved plan routes implementation to GPT-5.6 Luna at `max` by default,
   or GPT-5.6 Terra at `xhigh` for coherent cross-system/high-risk work.
4. Codex independently checks the resulting artifacts and success criteria.

Sol chooses the route before approval. Terra is not selected merely because a
task has many files: Sol first tries to express it as sequential Luna-sized
steps. You can override routing with `Use Luna` or `Use Terra`. Only the selected
implementer writes to the workspace.

## Use

Approval-gated:

```text
$sol-plan-implement Add pagination to the audit log API.
```

Automatic handoff:

```text
$sol-plan-implement Add pagination to the audit log API. Auto-approve the plan.
```

Forced route:

```text
$sol-plan-implement Refactor the storage and API layers. Use Terra.
```

Every gated response includes a plan ID and the selected route. Revision
feedback returns to the same Sol planner with a new plan ID. Validation repair
returns to the same selected implementer. A blocked Luna run never silently
switches to Terra; takeover requires a revised Sol plan.

Plan auto-approval does not bypass Codex confirmations for destructive actions,
external writes, credentials, purchases, or material scope expansion.

## Verify locally

```bash
python3 -m unittest -v tests/test_contract.py
python3 tests/live_smoke.py plan-id luna-auto terra-route ambiguous-gate revision-rejection
```
