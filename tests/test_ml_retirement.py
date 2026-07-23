"""Retirement of the May-9 lgbm_intraday LightGBM model (ML-001 closed,
2026-07-23). A "retired" marker in verification_report.json must make
ml_engine._get_model() and signal_guards.check_model_freshness() skip the
SARATHI-ML gate / freshness banner entirely and fall back to the same
neutral behavior callers already survive on -- with no gate call, no
ModelBlockedError, no exception.

Run: python3 -m pytest tests/test_ml_retirement.py -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from prototype.v4 import ml_engine  # noqa: E402
from prototype.utils import signal_guards  # noqa: E402
from scripts.team.gates import mlops_ic_gate  # noqa: E402


def _write_report(path: Path, retired=True, overall="BLOCK", override=None):
    report = {
        "model_path": "prototype/v4/models/lgbm_intraday.txt",
        "overall": overall,
        "blocking_rules": ["ML-001"] if overall == "BLOCK" else [],
    }
    if override:
        report["override"] = override
    if retired:
        report["retired"] = {
            "ts": "2026-07-23",
            "by": "soumya",
            "reason": "selection-neutral (IC 0.006); ML_SCORE_WEIGHT=0 fleet-wide",
        }
    path.write_text(json.dumps(report), encoding="utf-8")


class _TmpModelDir(unittest.TestCase):
    """Redirects ml_engine.MODEL_PATH at a scratch dir with a dummy model
    file + verification_report.json, and resets the module-level model
    cache so each test starts cold."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.model_dir = Path(self._tmpdir.name)
        self.model_path = self.model_dir / "lgbm_intraday.txt"
        self.model_path.write_text("dummy", encoding="utf-8")
        self.vr_path = self.model_dir / "verification_report.json"

        self._patch_model_path = mock.patch.object(ml_engine, "MODEL_PATH", self.model_path)
        self._patch_model_path.start()
        self.addCleanup(self._patch_model_path.stop)

        # reset cached model between tests
        ml_engine._loaded_model = None
        self.addCleanup(setattr, ml_engine, "_loaded_model", None)


class TestMlEngineRetiredPath(_TmpModelDir):
    def test_get_model_skips_gate_and_returns_none(self):
        _write_report(self.vr_path, retired=True)
        with mock.patch.object(mlops_ic_gate, "ensure_model_allowed") as gate_mock:
            model = ml_engine._get_model()
        self.assertIsNone(model)
        gate_mock.assert_not_called()

    def test_predict_ml_score_neutral_no_exception(self):
        _write_report(self.vr_path, retired=True)
        with mock.patch.object(mlops_ic_gate, "ensure_model_allowed") as gate_mock:
            score = ml_engine.predict_ml_score("RELIANCE", {})
        self.assertEqual(score, 0.5)
        gate_mock.assert_not_called()

    def test_predict_batch_neutral_no_exception(self):
        _write_report(self.vr_path, retired=True)
        with mock.patch.object(mlops_ic_gate, "ensure_model_allowed") as gate_mock:
            scores = ml_engine.predict_batch([("A", {}), ("B", {})])
        self.assertEqual(scores, [0.5, 0.5])
        gate_mock.assert_not_called()


class TestMlEngineUnretiredPathUnchanged(_TmpModelDir):
    """Existing behavior preserved: no 'retired' key -> gate is still
    consulted exactly as before."""

    def test_get_model_still_calls_gate_when_not_retired(self):
        _write_report(self.vr_path, retired=False, overall="BLOCK")
        with mock.patch.object(
            mlops_ic_gate, "ensure_model_allowed",
            side_effect=mlops_ic_gate.ModelBlockedError("test block"),
        ) as gate_mock:
            with self.assertRaises(mlops_ic_gate.ModelBlockedError):
                ml_engine._get_model()
        gate_mock.assert_called_once()


class TestCheckModelFreshnessRetired(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.model_dir = Path(self._tmpdir.name)
        self.model_path = self.model_dir / "lgbm_intraday.txt"
        self.model_path.write_text("dummy", encoding="utf-8")
        self.vr_path = self.model_dir / "verification_report.json"

    def _make_stale(self, days=100):
        import os
        import time
        stale_ts = time.time() - days * 86400
        os.utime(self.model_path, (stale_ts, stale_ts))

    def test_retired_marker_skips_freshness_check_silently(self):
        self._make_stale(100)  # would normally trip the stale-model abort
        _write_report(self.vr_path, retired=True)
        with mock.patch.object(signal_guards, "send_telegram_alert") as alert_mock:
            result = signal_guards.check_model_freshness(
                model_path=self.model_path, max_age_days=3, alert=True, abort=True)
        self.assertTrue(result)
        alert_mock.assert_not_called()

    def test_unretired_stale_model_still_aborts(self):
        """Existing behavior preserved: stale + not retired + no override
        still raises SystemExit."""
        self._make_stale(100)
        _write_report(self.vr_path, retired=False)
        with mock.patch.object(signal_guards, "send_telegram_alert"):
            with self.assertRaises(SystemExit):
                signal_guards.check_model_freshness(
                    model_path=self.model_path, max_age_days=3, alert=True, abort=True)


if __name__ == "__main__":
    unittest.main()
