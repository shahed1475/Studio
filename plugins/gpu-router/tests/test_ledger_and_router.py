"""Tests for the two pieces that must not be wrong: the quota window and routing."""
from __future__ import annotations

import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path

os.environ["ROUTER_DB"] = str(Path(tempfile.mkdtemp()) / "test.db")

from gpu_router import config, ledger, router  # noqa: E402


class WeekWindow(unittest.TestCase):
    def test_saturday_is_its_own_week_start(self):
        sat = dt.datetime(2026, 11, 28, 9, 30, tzinfo=dt.timezone.utc)  # a Saturday
        self.assertEqual(ledger.kaggle_week_start(sat),
                         dt.datetime(2026, 11, 28, 0, 0, tzinfo=dt.timezone.utc))

    def test_friday_looks_back_six_days(self):
        fri = dt.datetime(2026, 11, 27, 23, 59, tzinfo=dt.timezone.utc)
        self.assertEqual(ledger.kaggle_week_start(fri),
                         dt.datetime(2026, 11, 21, 0, 0, tzinfo=dt.timezone.utc))

    def test_sunday_looks_back_one_day(self):
        sun = dt.datetime(2026, 11, 29, 1, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(ledger.kaggle_week_start(sun),
                         dt.datetime(2026, 11, 28, 0, 0, tzinfo=dt.timezone.utc))

    def test_every_weekday_lands_on_a_saturday(self):
        for day in range(1, 29):
            when = dt.datetime(2026, 11, day, 12, 0, tzinfo=dt.timezone.utc)
            self.assertEqual(ledger.kaggle_week_start(when).weekday(), 5)


class QuotaAccounting(unittest.TestCase):
    def setUp(self):
        conn = ledger.connect()
        conn.execute("DELETE FROM runs")
        conn.close()

    def test_running_jobs_reserve_their_estimate(self):
        before = ledger.kaggle_usage("gpu").used_hours
        ledger.start_run("kaggle", "gpu", "render", est_hours=4.0)
        after = ledger.kaggle_usage("gpu").used_hours
        self.assertAlmostEqual(after - before, 4.0, places=3)

    def test_finished_job_uses_actual_not_estimate(self):
        run = ledger.start_run("kaggle", "gpu", "render", est_hours=9.0)
        ledger.finish_run(run, "complete", actual_hours=2.0)
        self.assertAlmostEqual(ledger.kaggle_usage("gpu").used_hours, 2.0, places=3)

    def test_cancelled_job_frees_its_quota(self):
        run = ledger.start_run("kaggle", "gpu", "render", est_hours=5.0)
        ledger.finish_run(run, "cancelled", actual_hours=5.0)
        self.assertAlmostEqual(ledger.kaggle_usage("gpu").used_hours, 0.0, places=3)

    def test_gpu_and_tpu_are_separate_pools(self):
        ledger.start_run("kaggle", "gpu", "render", est_hours=25.0)
        self.assertAlmostEqual(ledger.kaggle_usage("tpu").used_hours, 0.0, places=3)

    def test_duplicate_job_key_is_refused(self):
        ledger.start_run("kaggle", "gpu", "render", est_hours=1.0, job_key="shot-001")
        with self.assertRaises(ledger.DuplicateJob):
            ledger.start_run("kaggle", "gpu", "render", est_hours=1.0, job_key="shot-001")

    def test_stale_run_is_reaped_and_stops_holding_quota(self):
        run = ledger.start_run("kaggle", "gpu", "render", est_hours=8.0)
        conn = ledger.connect()
        old = (ledger.utcnow() - dt.timedelta(hours=20)).isoformat()
        conn.execute("UPDATE runs SET started_at = ? WHERE id = ?", (old, run))
        conn.close()
        self.assertEqual(ledger.reap_stale(), 1)
        row = ledger.connect().execute("SELECT status FROM runs WHERE id = ?", (run,)).fetchone()
        self.assertEqual(row["status"], "error")


def J(*a, **k):
    """A personal (non-commercial) job: the only kind Kaggle's terms allow without written permission."""
    return router.Job(*a, commercial=False, **k)


class Routing(unittest.TestCase):
    def setUp(self):
        conn = ledger.connect()
        conn.execute("DELETE FROM runs")
        conn.close()
        self._modal = config.MODAL_ENABLED
        config.MODAL_ENABLED = True  # these tests cover the original shape routing with Modal switched on

    def tearDown(self):
        config.MODAL_ENABLED = self._modal

    def test_cpu_job_costs_no_quota(self):
        d = router.choose(J("assemble", est_minutes=30, needs_gpu=False))
        self.assertEqual(d.backend, "cpu")

    def test_short_job_goes_to_per_second_backend(self):
        d = router.choose(J("infer", est_minutes=2))
        self.assertEqual(d.backend, "modal")

    def test_long_job_goes_to_kaggle(self):
        d = router.choose(J("render", est_minutes=240))
        self.assertEqual((d.backend, d.accelerator), ("kaggle", "gpu"))

    def test_job_longer_than_session_cap_is_split(self):
        d = router.choose(J("render", est_minutes=20 * 60))
        self.assertEqual(d.backend, "kaggle")
        self.assertEqual(d.split_runs, 2)  # 20 h over a 12 h cap

    def test_falls_through_to_modal_when_kaggle_is_spent(self):
        ledger.start_run("kaggle", "gpu", "render", est_hours=29.5)
        d = router.choose(J("render", est_minutes=60))
        self.assertEqual(d.backend, "modal")

    def test_defers_when_everything_is_spent(self):
        ledger.start_run("kaggle", "gpu", "render", est_hours=29.5)
        ledger.finish_run(
            ledger.start_run("modal", "gpu", "infer", est_hours=1.0),
            "complete", actual_hours=1.0, cost_usd=config.MODAL_MONTHLY_CREDIT_USD,
        )
        d = router.choose(J("render", est_minutes=120))
        self.assertEqual(d.backend, "defer")
        self.assertFalse(d.ok)

    def test_safety_margin_blocks_a_job_that_exactly_fills_the_quota(self):
        ledger.start_run("kaggle", "gpu", "render", est_hours=29.0)
        d = router.choose(J("render", est_minutes=60))  # 1 h left, 1 h margin
        self.assertNotEqual(d.backend, "kaggle")


if __name__ == "__main__":
    unittest.main(verbosity=2)
