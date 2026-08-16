---
name: sol-plan-implement
description: Use when the user explicitly wants GPT-5.6 Sol to plan implementation work and GPT-5.6 Luna to implement the approved plan, including follow-up approval, revision, rejection, or repair turns for that workflow. Human approval is the default; automatic implementation requires unmistakable request-level opt-in.
---

# Sol Plans, Luna Implements

Run a sequential two-agent workflow. Give Sol ownership of planning and Luna
ownership of implementation. Coordinate both stages without editing the target
workspace from the controller thread.

## Preserve These Invariants

- Human plan approval is the default.
- Ambiguity means `AUTO_APPROVE = false`.
- Let Sol inspect in-scope evidence, but never let Sol modify files or external
  state.
- Make Luna the sole workflow agent allowed to modify the target workspace.
- Never substitute another model or lower either reasoning effort.
- Normal Codex safety approvals still apply in every mode.
- Preserve unrelated and user-owned changes.
- Use isolated forks and explicit context packets; never rely on inherited chat
  history.

## Determine the Workflow State

Determine whether the current turn starts a new request, approves a plan,
revises a plan, rejects a plan, or repairs an implementation.

For a new request, capture these values from the current thread:

- `ORIGINAL_REQUEST`: the requested implementation outcome.
- `TARGET_WORKSPACE`: the actual repository or working directory.
- `CONSTRAINTS`: applicable user instructions, `AGENTS.md` rules, safety
  boundaries, dirty-worktree facts, and required validation.
- `RELEVANT_CONTEXT`: prior decisions and evidence needed to understand the
  task.

Exclude secrets and irrelevant conversation text from every context packet.

Set `AUTO_APPROVE = true` only when the user unmistakably asks to approve the
plan automatically or implement immediately after planning without a plan
review pause. Treat phrases such as "auto-approve the plan", "implement
automatically after planning", and "do not wait for plan approval" as opt-ins.
Do not treat negated, quoted, hypothetical, or ambiguous mentions as opt-ins.
Treat Codex CLI's `--approve-for-me` as a tool-approval setting, never as plan
auto-approval.

For a follow-up approval, revision, or rejection, identify the exact current
plan and saved Sol target from the thread. Never apply a response to an older or
ambiguous plan.

## Run the Planning Stage

For a new request, call `spawn_agent` with these exact settings:

```toml
task_name = "sol_planner"
fork_turns = "none"
model = "gpt-5.6-sol"
reasoning_effort = "xhigh"
```

Build the planner message from `ORIGINAL_REQUEST`, `TARGET_WORKSPACE`,
`CONSTRAINTS`, and `RELEVANT_CONTEXT`. Instruct Sol to:

1. Work only as the planning stage.
2. Inspect the real repository and relevant evidence before choosing steps.
3. Avoid editing files, installing dependencies, committing, or performing
   external writes.
4. Return Markdown sections named `Objective`, `Repository Findings`,
   `Assumptions`, `Files`, `Implementation Steps`, `Validation`, `Risks`, and
   `Open Questions`.
5. Make every step concrete enough for a separate implementation agent.
6. Report material ambiguity instead of inventing a requirement.

Save the returned target identifier as the current Sol planner. Wait for its
result with `wait_agent` using a long bounded wait. Never busy-poll. If a wait
ends without a final result, call `list_agents` once to reconcile status and
continue waiting only when Sol remains active.

Confirm that Sol returned an actionable plan with implementation and validation
steps. If planning fails or a material open question remains, report it and do
not start Luna.

## Enforce the Approval Gate

When `AUTO_APPROVE = false`, present Sol's complete plan and end the turn with:

> Approval required: approve this plan to send it to Luna, request revisions to
> send feedback back to Sol, or reject it to stop.

Do not spawn Luna before approval of the exact current plan.

Stop without implementation edits when the user rejects the plan.

When the user requests changes, call `followup_task` to resume the same Sol
planner with the exact feedback. Require a complete revised plan, never a patch
or delta. Present the revised plan and apply the approval gate again. Bypass the
new gate only when the revision request itself unmistakably sets
`AUTO_APPROVE = true`.

Proceed to implementation only when the user explicitly approves the current
plan or the request unmistakably sets `AUTO_APPROVE = true`.

## Run the Implementation Stage

Call `spawn_agent` with these exact settings:

```toml
task_name = "luna_implementer"
fork_turns = "none"
model = "gpt-5.6-luna"
reasoning_effort = "max"
```

Build Luna's message from `ORIGINAL_REQUEST`, `TARGET_WORKSPACE`, `CONSTRAINTS`,
and the complete approved plan. Instruct Luna to:

1. Work as the sole implementation agent without delegating or spawning
   writers.
2. Inspect current state before editing and preserve unrelated changes.
3. Implement only the approved scope and use apply-patch-style edits where
   available.
4. Run every relevant validation check that is safe and available.
5. Preserve the goal and document any small adaptation required by repository
   evidence. Stop for approval before material scope expansion.
6. Return `Status`, `Changed Files`, `Validation`, `Plan Deviations`, and
   `Blockers` sections with concrete evidence.

Save the returned target identifier as the current Luna implementer. Wait with
the same long-wait and single-reconciliation policy used for Sol.

## Repair Validation Failures

Require Luna's final result and current validation evidence. Never infer
completion from progress text.

When validation fails because of an in-scope implementation defect, call
`followup_task` to resume the same Luna implementer with the exact command,
failure output, and unchanged approved scope. Require Luna to repair the defect
and rerun validation. Repeat with the same Luna target until validation passes
or Luna is genuinely blocked.

When Luna is blocked, report the blocker, edits already made, workspace state,
validation already run, and the exact user decision or external change needed.
Never silently start a replacement agent.

## Return the Outcome

Lead with the outcome and include:

- whether the plan was human-approved or auto-approved;
- the implemented scope and changed files;
- validation commands and results;
- justified deviations from Sol's plan;
- anything that remains unverified or blocked.

Never describe an unrun live check as passing. Never claim a plugin, service,
or application is installed merely because its source files exist.
