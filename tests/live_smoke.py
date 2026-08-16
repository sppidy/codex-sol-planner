#!/usr/bin/env python3
"""Run end-to-end behavioral checks against the installed plugin."""

from __future__ import annotations

import argparse
import hashlib
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
    "approval-reuse",
    "no-progress",
)


def run_codex(
    case: str, prompt: str, *, ephemeral: bool = True
) -> tuple[Path, str, list[dict[str, object]]]:
    case_root = Path(tempfile.mkdtemp(prefix=f"codex-sol-planner-{case}."))
    root = case_root / "workspace"
    evidence = case_root / "evidence"
    root.mkdir()
    evidence.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    last_message = evidence / "last-message.md"
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
    (evidence / "events.jsonl").write_text(result.stdout)
    (evidence / "stderr.log").write_text(result.stderr)
    if result.returncode != 0:
        raise AssertionError(
            f"codex exec failed with {result.returncode}; evidence: {root}"
        )
    events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    return root, last_message.read_text(), events


def resume_codex(root: Path, thread_id: str, label: str, prompt: str) -> str:
    evidence = root.parent / "evidence"
    last_message = evidence / f"last-message-{label}.md"
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
    (evidence / f"events-{label}.jsonl").write_text(result.stdout)
    (evidence / f"stderr-{label}.log").write_text(result.stderr)
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


def workspace_snapshot(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if relative.parts[0] == ".git":
            continue
        key = relative.as_posix()
        if path.is_symlink():
            snapshot[key] = f"symlink:{path.readlink()}"
        elif path.is_dir():
            snapshot[f"{key}/"] = "directory"
        else:
            snapshot[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def assert_plan_id(message: str) -> None:
    extract_plan_id(message)


def plan_id() -> Path:
    before: dict[str, str] = {}
    root, message, _ = run_codex(
        "plan-id",
        "$sol-plan-implement Create result.txt containing exactly ready. "
        "Do not auto-approve the plan.",
    )
    if workspace_snapshot(root) != before:
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
    if workspace_snapshot(root):
        raise AssertionError("quoted auto-approval text changed the workspace")
    assert_plan_id(message)
    return root


def approval_reuse() -> Path:
    root, message, events = run_codex(
        "approval-reuse",
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
    if "revised" not in revised.lower():
        raise AssertionError("revised plan did not incorporate the requested content")
    if workspace_snapshot(root):
        raise AssertionError("plan revision changed the workspace")
    stale = resume_codex(
        root,
        str(thread_id),
        "stale-approval",
        f"Approve superseded plan {first_plan_id} and implement it.",
    )
    if workspace_snapshot(root):
        raise AssertionError("stale plan approval changed the workspace")
    if not re.search(r"(?i)stale|superseded|current plan|does not authorize", stale):
        raise AssertionError("stale approval was not explicitly refused")
    approved = resume_codex(
        root,
        str(thread_id),
        "current-approval",
        f"Approve current plan {revised_plan_id} and implement it now.",
    )
    if (root / "result.txt").read_text() != "revised":
        raise AssertionError("current plan approval did not implement the revision")
    if not re.search(r"(?i)approval mode[^\n]*human-approved", approved):
        raise AssertionError("current-ID implementation was not marked human-approved")
    after_first = workspace_snapshot(root)
    second = resume_codex(
        root,
        str(thread_id),
        "second-workflow",
        "$sol-plan-implement Create second.txt containing exactly second. "
        "Do not auto-approve this new plan.",
    )
    second_plan_id = extract_plan_id(second)
    if second_plan_id == revised_plan_id:
        raise AssertionError("second workflow reused the previous plan ID")
    if workspace_snapshot(root) != after_first:
        raise AssertionError("second gated workflow changed the workspace")
    rejected = resume_codex(
        root,
        str(thread_id),
        "second-rejection",
        f"Reject plan {second_plan_id}. Stop without creating second.txt.",
    )
    if workspace_snapshot(root) != after_first:
        raise AssertionError("second-plan rejection changed the workspace")
    if not re.search(r"(?i)reject|stopp?ed|no implementation", rejected):
        raise AssertionError("second rejection did not confirm workflow termination")
    return root


def no_progress() -> Path:
    root, message, _ = run_codex(
        "no-progress",
        "$sol-plan-implement Run a deliberate no-progress controller smoke test. "
        "Auto-approve the plan and use Luna. Luna's initial pass must create "
        "result.txt containing exactly wrong with no newline, while the approved "
        "SC and controller validation require it to contain exactly ready. On the "
        "repair follow-up, Luna must leave the workspace unchanged and return the "
        "same failing command, exit 1, and normalized error 'content mismatch'. "
        "The controller must stop when that fingerprint is observed twice total, "
        "must not switch models, and must report the no-progress blocker.",
    )
    if (root / "result.txt").read_text() != "wrong":
        raise AssertionError("no-progress fixture did not preserve the failed output")
    if not re.search(r"(?im)^implementation route:\s*luna\b", message):
        raise AssertionError("no-progress workflow switched away from Luna")
    if not re.search(r"(?im)^repair attempts:\s*1\s*$", message):
        raise AssertionError("no-progress workflow did not stop after one repair")
    if not re.search(r"(?im)^no-progress:\s*blocked\s*$", message):
        raise AssertionError("no-progress workflow did not report the blocker")
    return root


RUNNERS = {
    "plan-id": plan_id,
    "terra-route": terra_route,
    "luna-auto": luna_auto,
    "ambiguous-gate": ambiguous_gate,
    "approval-reuse": approval_reuse,
    "no-progress": no_progress,
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
