# Codex Sol Planner

`codex-sol-planner` provides the `$sol-plan-implement` workflow:

1. GPT-5.6 Sol at `xhigh` inspects the project and writes an implementation
   plan.
2. Codex asks you to approve that plan by default.
3. GPT-5.6 Luna at `max` implements and validates the approved plan.

## Use

Approval-gated:

```text
$sol-plan-implement Add pagination to the audit log API.
```

Automatic handoff:

```text
$sol-plan-implement Add pagination to the audit log API. Auto-approve the plan.
```

You can request plan revisions before approval. Revision feedback goes back to
the same Sol planner. If implementation validation fails, correction stays with
the same Luna implementer.

Plan auto-approval does not bypass Codex confirmations for destructive actions,
external writes, credentials, purchases, or material scope expansion.
