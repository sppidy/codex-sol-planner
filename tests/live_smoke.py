#!/usr/bin/env python3
"""Run end-to-end behavioral checks against the installed plugin."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile


CASES = (
    "plan-id",
    "terra-route",
    "luna-auto",
    "ambiguous-gate",
    "revision-rejection",
)


def run_codex(
    case: str, prompt: str, *, ephemeral: bool = True
) -> tuple[Path, str, list[dict[str, object]]]:
    root = Path(tempfile.mkdtemp(prefix=f"codex-sol-planner-{case}."))
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    last_message = root / "last-message.md"
    command = [
        "codex",
        "exec",
    ]
    if ephemeral:
        command.append("--ephemeral")
    command.extend(
        [
            "--approve-for-me",
            "--json",
            "-o",
            str(last_message),
            "-C",
            str(root),
            prompt,
        ]
    )
    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=900,
    )
    (root / "events.jsonl").write_text(result.stdout)
    (root / "stderr.log").write_text(result.stderr)
    if result.returncode != 0:
        raise AssertionError(
            f"codex exec failed with {result.returncode}; evidence: {root}"
        )
    events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    return root, last_message.read_text(), events


def resume_codex(root: Path, thread_id: str, label: str, prompt: str) -> str:
    last_message = root / f"last-message-{label}.md"
    result = subprocess.run(
        [
            "codex",
            "exec",
            "resume",
            "--json",
            "-o",
            str(last_message),
            thread_id,
            prompt,
        ],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=900,
    )
    (root / f"events-{label}.jsonl").write_text(result.stdout)
    (root / f"stderr-{label}.log").write_text(result.stderr)
    if result.returncode != 0:
        raise AssertionError(
            f"codex resume {label} failed with {result.returncode}; evidence: {root}"
        )
    return last_message.read_text()


def extract_plan_id(message: str) -> str:
    match = re.search(r"(?im)^plan id:\s*(sol-[a-z0-9-]+)\s*$", message)
    if not match:
        raise AssertionError("response did not expose a canonical Plan ID line")
    return match.group(1)


def assert_plan_id(message: str) -> None:
    extract_plan_id(message)


def plan_id() -> Path:
    root, message, _ = run_codex(
        "plan-id",
        "$sol-plan-implement Create result.txt containing exactly ready. "
        "Do not auto-approve the plan.",
    )
    if (root / "result.txt").exists():
        raise AssertionError("approval-gated request changed the workspace")
    assert_plan_id(message)
    if not re.search(r"(?im)^implementation route:\s*luna\b", message):
        raise AssertionError("gated plan did not expose the selected Luna route")
    return root


def terra_route() -> Path:
    root, message, _ = run_codex(
        "terra-route",
        "$sol-plan-implement Create schema.sql, api.txt, worker.txt, and ui.txt, "
        "each containing exactly its own filename. This is one tightly coupled "
        "database/API/worker/UI change. Use Terra for implementation, auto-approve "
        "the plan, and implement automatically.",
    )
    for name in ("schema.sql", "api.txt", "worker.txt", "ui.txt"):
        if (root / name).read_text() != name:
            raise AssertionError(f"{name} did not contain exactly its filename")
    if not re.search(r"(?i)implementation route[^\n]*terra", message):
        raise AssertionError("final outcome did not identify Terra as implementer")
    return root


def luna_auto() -> Path:
    root, message, _ = run_codex(
        "luna-auto",
        "$sol-plan-implement Create result.txt containing exactly ready. "
        "Auto-approve the plan and implement automatically.",
    )
    if (root / "result.txt").read_text() != "ready":
        raise AssertionError("Luna auto-approved request did not produce exact output")
    if not re.search(r"(?i)implementation route[^\n]*luna", message):
        raise AssertionError("final outcome did not identify Luna as implementer")
    return root


def ambiguous_gate() -> Path:
    root, message, _ = run_codex(
        "ambiguous-gate",
        "$sol-plan-implement Create result.txt containing exactly ready. The phrase "
        "'auto-approve the plan' is quoted as an example; do not auto-approve mine.",
    )
    if (root / "result.txt").exists():
        raise AssertionError("quoted auto-approval text bypassed the approval gate")
    assert_plan_id(message)
    return root


def revision_rejection() -> Path:
    root, message, events = run_codex(
        "revision-rejection",
        "$sol-plan-implement Create result.txt containing exactly ready. "
        "Do not auto-approve the plan.",
        ephemeral=False,
    )
    first_plan_id = extract_plan_id(message)
    thread_id = next(
        event["thread_id"]
        for event in events
        if event.get("type") == "thread.started"
    )
    revised = resume_codex(
        root,
        str(thread_id),
        "revision",
        "Revise the current plan so result.txt will contain exactly revised "
        "instead of ready. Do not auto-approve the revised plan.",
    )
    revised_plan_id = extract_plan_id(revised)
    if revised_plan_id == first_plan_id:
        raise AssertionError("plan revision reused the stale plan ID")
    if "exactly revised" not in revised.lower():
        raise AssertionError("revised plan did not incorporate the requested content")
    if (root / "result.txt").exists():
        raise AssertionError("plan revision bypassed approval and edited the workspace")
    rejected = resume_codex(
        root,
        str(thread_id),
        "rejection",
        f"Reject plan {revised_plan_id}. Stop without creating any files.",
    )
    if (root / "result.txt").exists():
        raise AssertionError("plan rejection edited the workspace")
    if not re.search(r"(?i)reject|stopp?ed|no implementation", rejected):
        raise AssertionError("rejection response did not confirm workflow termination")
    return root


RUNNERS = {
    "plan-id": plan_id,
    "terra-route": terra_route,
    "luna-auto": luna_auto,
    "ambiguous-gate": ambiguous_gate,
    "revision-rejection": revision_rejection,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cases", nargs="*", choices=CASES, default=list(CASES))
    args = parser.parse_args()
    for case in args.cases:
        evidence = RUNNERS[case]()
        print(f"PASS {case}: {evidence}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
