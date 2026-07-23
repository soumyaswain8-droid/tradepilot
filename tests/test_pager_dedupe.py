"""Pager dedupe regression (2026-07-23): the ML-001 override expiry turned
one policy state into 1,248 identical Telegram pages (one per gate check per
engine per scan). log_audit's pager must page once per unique block
signature per cooldown window, count suppressed repeats, and re-page with
the count after cooldown. Run: python3 -m pytest tests/test_pager_dedupe.py -v
"""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "team_log", str(PROJECT_ROOT / "scripts" / "team" / "log.py"))
team_log = importlib.util.module_from_spec(_spec)
sys.modules["team_log"] = team_log
_spec.loader.exec_module(team_log)


def _audit(**kw):
    d = dict(agent="mlops-sentinel", action="ensure-allowed", decision="BLOCK",
             subject="/models/lgbm_intraday.txt", evidence={},
             reason="Model BLOCKED. Blocking rules: ['ML-001']",
             vetoable_by=["CEO"], rule_family="SARATHI-ML")
    d.update(kw)
    return d


class TestPagerDedupe(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        # redirect all log targets + pager state into the tmp dir
        for attr in ("ACTIVITY_DIR", "AUDIT_DIR", "SARATHI_DIR", "STATUS_DIR"):
            (tmp / attr).mkdir()
            self._patch(attr, tmp / attr)
        self._patch("_PAGER_STATE", tmp / "pager_state.json")
        # stub the telegram module so the function-level import resolves to us
        self.sent = []
        stub = types.ModuleType("prototype.v5.telegram_bot")
        stub.send_alert = lambda msg: self.sent.append(msg)
        pkg_proto = types.ModuleType("prototype")
        pkg_v5 = types.ModuleType("prototype.v5")
        for name, m in (("prototype", pkg_proto), ("prototype.v5", pkg_v5),
                        ("prototype.v5.telegram_bot", stub)):
            self._sys_patch(name, m)

    def _patch(self, attr, value):
        p = mock.patch.object(team_log, attr, value)
        p.start()
        self.addCleanup(p.stop)

    def _sys_patch(self, name, module):
        p = mock.patch.dict(sys.modules, {name: module})
        p.start()
        self.addCleanup(p.stop)

    def test_first_block_pages(self):
        team_log.log_audit(**_audit())
        self.assertEqual(len(self.sent), 1)

    def test_identical_repeats_suppressed(self):
        for _ in range(50):
            team_log.log_audit(**_audit())
        self.assertEqual(len(self.sent), 1)

    def test_different_signature_pages_separately(self):
        team_log.log_audit(**_audit())
        team_log.log_audit(**_audit(subject="/models/other_model.txt"))
        self.assertEqual(len(self.sent), 2)

    def test_pass_decisions_never_page(self):
        team_log.log_audit(**_audit(decision="PASS", vetoable_by=[]))
        self.assertEqual(self.sent, [])

    def test_cooldown_expiry_repages_with_suppressed_count(self):
        team_log.log_audit(**_audit())
        for _ in range(7):
            team_log.log_audit(**_audit())
        # age the stored signature past the cooldown window
        state_file = team_log._PAGER_STATE
        state = json.loads(state_file.read_text())
        for sig in state:
            state[sig]["last_sent"] -= team_log._PAGER_COOLDOWN_S + 1
        state_file.write_text(json.dumps(state))
        team_log.log_audit(**_audit())
        self.assertEqual(len(self.sent), 2)
        self.assertIn("repeated 7x since last page", self.sent[1])

    def test_dedupe_failure_fails_open_to_sending(self):
        # a broken state path must never swallow the page itself
        self._patch("_PAGER_STATE", Path("/nonexistent-dir/x/y/state.json"))
        team_log.log_audit(**_audit())
        self.assertEqual(len(self.sent), 1)

    def test_audit_jsonl_still_written_every_time(self):
        for _ in range(3):
            team_log.log_audit(**_audit())
        day_file = next(team_log.AUDIT_DIR.glob("*.jsonl"))
        self.assertEqual(len(day_file.read_text().strip().splitlines()), 3)


if __name__ == "__main__":
    unittest.main()
