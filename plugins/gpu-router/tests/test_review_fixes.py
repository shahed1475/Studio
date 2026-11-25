"""Fixes from the Story Studio review of 25 Nov 2026 (plugins/gpu-router/REVIEW_2026-11-25.md). Fakes only: no Kaggle or Modal call."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ROUTER_DB", str(Path(tempfile.mkdtemp()) / "test.db"))

from gpu_router import config, ledger, router  # noqa: E402
from gpu_router.backends import kaggle_backend as kb  # noqa: E402

# Real output of Kaggle CLI 2.2.5, recorded 24 Nov 2026 on the owner's account.
REAL_COMPLETE = 'shahedalfahad/studio-job-8ba727ef5f45c77c has status "KernelWorkerStatus.COMPLETE"'
REAL_QUEUED = 'shahedalfahad/studio-job-136f1b32068c72a8 has status "KernelWorkerStatus.QUEUED"'
REAL_CANCEL = 'shahedalfahad/studio-job-136f1b32068c72a8 has status "KernelWorkerStatus.CANCEL_ACKNOWLEDGED"'
REAL_QUOTA = ('[{"resource": "GPU", "used": "11.88h", "remaining": "18.12h", "total": "30.00h", "refreshAt": "2026-11-28T00:00:00+00:00"},'
              ' {"resource": "TPU", "used": "0.00h", "remaining": "20.00h", "total": "20.00h", "refreshAt": "2026-11-28T00:00:00+00:00"}]')


class StatusParsing(unittest.TestCase):
    def test_real_cli_2x_statuses_are_read(self):
        self.assertEqual(kb.parse_status(REAL_COMPLETE), "complete")
        self.assertIn(kb.parse_status(REAL_COMPLETE), kb.TERMINAL_OK)
        self.assertEqual(kb.parse_status(REAL_QUEUED), "queued")
        self.assertIn(kb.parse_status(REAL_CANCEL), kb.TERMINAL_BAD)

    def test_older_cli_text_and_garbage(self):
        self.assertEqual(kb.parse_status('me/k has status "complete"'), "complete")
        self.assertEqual(kb.parse_status("nothing useful"), "unknown")


class PushAndQuota(unittest.TestCase):
    def setUp(self):
        self.calls, self._run = [], kb._run

    def tearDown(self):
        kb._run = self._run

    def test_push_sends_the_chosen_accelerator_and_time_cap(self):
        d = Path(tempfile.mkdtemp())
        (d / "kernel-metadata.json").write_text('{"id": "me/slug", "enable_gpu": true, "enable_internet": true}')
        kb._run = lambda args, timeout=600: self.calls.append(args) or ""
        self.assertEqual(kb.push(d, accelerator="gpu", timeout_s=900), "me/slug")
        self.assertEqual(self.calls[0][-4:], ["--accelerator", "NvidiaTeslaT4", "-t", "900"])

    def test_real_quota_reads_kaggles_own_numbers(self):
        kb._run = lambda args, timeout=600: REAL_QUOTA
        q = kb.real_quota()
        self.assertAlmostEqual(q["gpu"], 18.12)
        self.assertAlmostEqual(q["tpu"], 20.0)

    def test_real_quota_is_none_when_the_cli_cannot_say(self):
        def fail(args, timeout=600):
            raise kb.KaggleError("no network")
        kb._run = fail
        self.assertIsNone(kb.real_quota())


class TermsAndMoney(unittest.TestCase):
    def setUp(self):
        conn = ledger.connect()
        conn.execute("DELETE FROM runs")
        conn.close()
        self._ref, self._modal = config.KAGGLE_COMMERCIAL_PERMISSION_REF, config.MODAL_ENABLED
        config.KAGGLE_COMMERCIAL_PERMISSION_REF, config.MODAL_ENABLED = "", False

    def tearDown(self):
        config.KAGGLE_COMMERCIAL_PERMISSION_REF, config.MODAL_ENABLED = self._ref, self._modal

    def test_a_commercial_render_never_goes_to_kaggle_without_written_permission(self):
        d = router.choose(router.Job("render", est_minutes=240))  # commercial is the default
        self.assertEqual(d.backend, "defer")
        self.assertIn("non-commercial", d.reason)

    def test_a_personal_job_may_use_kaggle(self):
        d = router.choose(router.Job("benchmark", est_minutes=240, commercial=False))
        self.assertEqual((d.backend, d.accelerator), ("kaggle", "gpu"))

    def test_a_recorded_written_permission_lets_commercial_work_through(self):
        config.KAGGLE_COMMERCIAL_PERMISSION_REF = "Kaggle support ticket 123, 2026-12-01"
        self.assertEqual(router.choose(router.Job("render", est_minutes=240)).backend, "kaggle")

    def test_modal_is_never_chosen_while_switched_off(self):
        d = router.choose(router.Job("infer", est_minutes=2, commercial=False))
        self.assertNotEqual(d.backend, "modal")

    def test_kaggles_own_remaining_hours_cap_the_ledgers_estimate(self):
        d = router.choose(router.Job("benchmark", est_minutes=5 * 60, commercial=False), live={"gpu": 3.0, "tpu": 20.0})
        self.assertNotEqual(d.backend, "kaggle")  # the ledger alone would say 30 h are left
        d = router.choose(router.Job("benchmark", est_minutes=60, commercial=False), live={"gpu": 3.0, "tpu": 20.0})
        self.assertEqual(d.backend, "kaggle")


if __name__ == "__main__":
    unittest.main(verbosity=2)
