---
name: sol-plan-implement
description: "Use for the Sol-plan/Luna-or-Terra-implement workflow, including approval, revision, rejection, and repair follow-ups. Human approval is default; auto-approval needs explicit request-level opt-in."
---

# Sol Plans; Luna or Terra Implements

Run one sequential workflow: Sol plans, the controller gates the exact plan,
and one selected implementer writes and validates it.

## Keep These Invariants

- Use Sol/xhigh for planning, Luna/max as the default implementer, and
  Terra/xhigh only for an approved complexity route or explicit user override.
- Keep Sol read-only. Let only the selected implementer edit source files.
- Never run Luna and Terra concurrently or silently substitute a model.
- Preserve normal Codex approvals, scope limits, dirty state, and user-owned
  changes in every mode.
- Spawn isolated agents with explicit context packets; do not rely on inherited
  chat history.
- Require final evidence. Progress text and agent success claims are not proof.

## Establish State

Classify the turn as a new request, plan approval, plan revision, plan
rejection, implementation repair, or blocked-workflow decision.

For a new request, capture:

- `ORIGINAL_REQUEST`: requested implementation outcome.
- `TARGET_WORKSPACE`: verified repository or working directory.
- `CONSTRAINTS`: user and `AGENTS.md` rules, safety boundaries, dirty-state
  facts, and required validation.
- `RELEVANT_CONTEXT`: decisions and evidence needed for this task only.
- `WORKFLOW_ID`: a new UTC timestamp with microseconds (`YYYYMMDDHHMMSSffffff`)
  for this request. Keep it unchanged through plan revisions and
  implementation repair.
- `PLAN_ID`: `sol-` plus a UTC timestamp with microseconds
  (`YYYYMMDDHHMMSSffffff`). Keep it unchanged for that plan and create a new,
  distinct one for every revision.
- `AUTO_APPROVE`: false unless the current request unmistakably opts in.
- `ROUTE_OVERRIDE`: `Luna`, `Terra`, or unset. Set it only for an explicit,
  unambiguous request such as "use Luna" or "use Terra".

Exclude secrets and irrelevant conversation from context packets.

Treat "auto-approve the plan", "implement automatically after planning", and
"do not wait for plan approval" as auto-approval opt-ins. Negated, quoted,
hypothetical, and ambiguous text is not an opt-in. CLI `--approve-for-me`
controls tool approvals, not this plan gate.

Bind follow-ups to the latest pending `PLAN_ID` and saved agent target. A plain
"approve" may approve the only unambiguous pending plan. If multiple or stale
plans could match, require the plan ID instead of guessing.

Use only these spawn routes. Replace `<workflow_id>` with `WORKFLOW_ID` before
calling `spawn_agent`; the resulting task name must contain only lowercase
letters, digits, and underscores. Always set `fork_turns = "none"`.

| Role | Task name | Model | Reasoning effort |
| --- | --- | --- | --- |
| Planner | `sol_planner_<workflow_id>` | `gpt-5.6-sol` | `xhigh` |
| Luna implementer | `luna_implementer_<workflow_id>` | `gpt-5.6-luna` | `max` |
| Terra implementer | `terra_implementer_<workflow_id>` | `gpt-5.6-terra` | `xhigh` |

Never reuse a task name from an earlier workflow in the same conversation.

## Ask Sol for the Plan

For a new request, call `spawn_agent` with the Planner row and the current
`WORKFLOW_ID`.

Send `PLAN_ID`, `ORIGINAL_REQUEST`, `TARGET_WORKSPACE`, `CONSTRAINTS`,
`RELEVANT_CONTEXT`, and `ROUTE_OVERRIDE`. Instruct Sol to:

1. Inspect in-scope evidence without editing files, installing dependencies,
   committing, or making external writes.
2. Return these Markdown sections: `Plan ID`, `Objective`, `Success Criteria`,
   `Repository Findings`, `Assumptions`, `Implementation Route`, `Files`,
   `Implementation Steps`, `Validation`, `Approval-Sensitive Actions`, `Risks`,
   and `Open Questions`.
3. Label measurable success criteria `SC-1`, `SC-2`, and so on.
4. Honor `ROUTE_OVERRIDE`. Otherwise choose Luna by default. Choose Terra only
   when coherent implementation needs substantial cross-subsystem or
   high-risk reasoning and cannot safely be expressed as sequential,
   Luna-sized steps. File count or a claim that work is "complex" is not enough.
5. Write the route as exactly `Luna — gpt-5.6-luna / max` or
   `Terra — gpt-5.6-terra / xhigh`, followed by a short evidence-based reason.
6. Provide concrete ordered steps and validation for a separate implementer.
   Report material ambiguity instead of inventing requirements.

Save Sol's target. Wait with one long bounded `wait_agent` call. If it returns
without a final result, use `list_agents` once to reconcile and continue only
when Sol remains active; never busy-poll.

Reject a plan as non-actionable when its plan ID differs, its route is invalid,
success criteria are not measurable, validation is missing, or a material open
question remains. Report the issue and do not start an implementer.

## Gate the Exact Plan

When `AUTO_APPROVE = false`, present the complete plan and end the turn with
these plain lines:

```text
Plan ID: sol-<timestamp>
Implementation route: Luna|Terra
Approval required: approve this plan, request revisions, or reject it.
```

Do not spawn an implementer before approval of that exact current plan. A
rejection stops without implementation edits.

For revisions, create a new `PLAN_ID` and call `followup_task` on the same Sol
target with the ID and exact feedback. Require a complete revised plan, present
it, and gate it again. Bypass the new gate only when the revision request itself
unmistakably enables auto-approval.

Proceed only after explicit approval of the current plan or request-level
auto-approval. Approval covers the named implementation route but never bypasses
ordinary safety confirmation.

## Run the Selected Implementer

Call `spawn_agent` with the approved Luna or Terra row and the current
`WORKFLOW_ID`. Spawn exactly one implementer. Send the complete approved plan
plus `ORIGINAL_REQUEST`, `TARGET_WORKSPACE`, and `CONSTRAINTS`. Instruct it to:

1. Be the sole writer and do not delegate or spawn writers.
2. Inspect current state, preserve unrelated changes, and implement only the
   approved scope using patch-style edits when available.
3. Run every safe, available validation check from the plan. Stop before
   material scope expansion or approval-sensitive action not already approved.
4. Return `Status`, `Changed Files`, `Success Criteria Evidence`, `Validation`,
   `Plan Deviations`, and `Blockers`. Map every `SC-N` to concrete pass, fail, or
   unverified evidence.

Save the implementer target. Use the same bounded wait and single-reconciliation
policy as for Sol.

## Verify and Repair

After the implementer returns, independently inspect the workspace from the
controller. Compare every success criterion with the reported evidence and
actual diff or artifacts. Rerun approved local validation when safe; expected
test/build byproducts are allowed, but the controller must not edit source.
Never convert an unavailable external or live check into a pass.

On an in-scope failure, call `followup_task` on the same implementer target with
the failing command, exit status, bounded output, unmet `SC-N`, and unchanged
approved scope. Require repair and validation rerun.

Track a failure fingerprint (command, exit status, and normalized error) plus a
workspace diff/status summary and count controller-requested repair attempts.
The controller must never repair source itself. If the same fingerprint is
observed twice total without a meaningful code or diagnostic change, stop after
the first repair attempt and report a no-progress blocker. Do not silently
switch from Luna to Terra. A takeover requires a fresh Sol plan and approval of
its new plan ID and route.

## Return the Outcome

Lead with the result and include these exact state lines:

```text
Plan ID: sol-<timestamp>
Approval mode: human-approved|auto-approved
Implementation route: Luna|Terra
Repair attempts: <integer>
No-progress: no|blocked
```

Then report changed files, evidence for every success criterion, validation
commands and results, justified deviations, and anything blocked or unverified.
Never call source presence an installation, or an unrun check a pass.
