#!/usr/bin/env python3
"""Static checks for model pins and package metadata.

Behavior remains covered by live_smoke.py; these checks protect exact fields that
the Codex runtime consumes but does not surface in its JSON event stream.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "sol-plan-implement" / "SKILL.md"
OPENAI_YAML = ROOT / "skills" / "sol-plan-implement" / "agents" / "openai.yaml"
MANIFEST = ROOT / ".codex-plugin" / "plugin.json"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL.read_text()
        cls.openai_yaml = OPENAI_YAML.read_text()
        cls.manifest = json.loads(MANIFEST.read_text())

    def test_exact_model_routes_are_pinned(self) -> None:
        for task, model, effort in (
            ("sol_planner", "gpt-5.6-sol", "xhigh"),
            ("luna_implementer", "gpt-5.6-luna", "max"),
            ("terra_implementer", "gpt-5.6-terra", "xhigh"),
        ):
            pattern = (
                rf'task_name = "{re.escape(task)}".*?'
                rf'model = "{re.escape(model)}".*?'
                rf'reasoning_effort = "{re.escape(effort)}"'
            )
            self.assertRegex(self.skill, re.compile(pattern, re.DOTALL))

    def test_plan_contract_names_decision_fields(self) -> None:
        for field in (
            "Plan ID",
            "Success Criteria",
            "Implementation Route",
            "Approval-Sensitive Actions",
            "Success Criteria Evidence",
        ):
            self.assertIn(field, self.skill)

    def test_repair_contract_prevents_silent_takeover_and_stalled_loops(self) -> None:
        self.assertIn("failure fingerprint", self.skill)
        self.assertIn("recurs twice", self.skill)
        self.assertIn("Do not silently switch from Luna to Terra", self.skill)
        self.assertRegex(self.skill, re.compile(r"fresh\s+Sol plan"))

    def test_public_metadata_identifies_v02_and_sppidy(self) -> None:
        self.assertRegex(self.manifest["version"], r"^0\.2\.0(?:\+|$)")
        self.assertEqual(self.manifest["author"]["name"], "sppidy")
        self.assertEqual(self.manifest["interface"]["developerName"], "sppidy")
        self.assertEqual(
            self.manifest["repository"],
            "https://github.com/sppidy/codex-sol-planner",
        )

    def test_ui_metadata_exposes_both_implementation_routes(self) -> None:
        self.assertRegex(self.openai_yaml, re.compile(r"Luna.*Terra", re.DOTALL))


if __name__ == "__main__":
    unittest.main()
