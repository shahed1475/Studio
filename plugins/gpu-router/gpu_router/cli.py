"""Command line entry point: gpu-router <command>."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ledger, router
from .backends import kaggle_backend


def cmd_quota(_args) -> int:
    ledger.reap_stale()
    print(ledger.report())
    return 0


def cmd_plan(args) -> int:
    job = router.Job(
        kind=args.kind,
        est_minutes=args.minutes,
        needs_gpu=not args.cpu,
        prefers_tpu=args.tpu,
        latency_sensitive=args.interactive,
        commercial=not args.personal,
    )
    decision = router.choose(job, kaggle_backend.real_quota())
    print(f"backend     : {decision.backend}")
    print(f"accelerator : {decision.accelerator}")
    print(f"reason      : {decision.reason}")
    if decision.split_runs > 1:
        print(f"split       : {decision.split_runs} checkpointed sessions "
              f"(job exceeds the hard session cap)")
    return 0 if decision.ok else 1


def cmd_submit(args) -> int:
    job_dir = Path(args.job_dir)
    job = router.Job(kind=args.kind, est_minutes=args.minutes, prefers_tpu=args.tpu, commercial=not args.personal)
    decision = router.choose(job, kaggle_backend.real_quota())
    print(f"-> {decision.backend}/{decision.accelerator}: {decision.reason}")
    if not decision.ok:
        print("nothing to do; requeue after the next quota reset", file=sys.stderr)
        return 1
    if decision.backend != "kaggle":
        print(f"{decision.backend} submission isn't wired to the CLI yet; "
              f"call gpu_router.backends.{decision.backend}_backend directly.",
              file=sys.stderr)
        return 2

    run_id = ledger.start_run(
        backend="kaggle", accelerator=decision.accelerator, job_kind=job.kind,
        est_hours=job.est_hours, job_key=args.job_key,
    )
    try:
        ref = kaggle_backend.push(job_dir, accelerator=decision.accelerator, timeout_s=args.timeout)
        ledger.set_external_id(run_id, ref)
        print(f"pushed {ref}")
        if args.wait:
            state = kaggle_backend.wait(ref, on_poll=lambda s: print(f"  ... {s}"))
            kaggle_backend.output(ref, Path(args.out or "./out"))
            ledger.finish_run(run_id, status="complete")
            print(f"{ref} {state}; artifacts in {args.out or './out'}")
        else:
            print(f"poll with: gpu-router poll {ref} --run-id {run_id}")
    except Exception as exc:
        ledger.finish_run(run_id, status="error", notes=str(exc)[:500])
        print(f"failed: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_poll(args) -> int:
    state = kaggle_backend.status(args.ref)
    print(state)
    if args.run_id and state in kaggle_backend.TERMINAL_OK:
        ledger.finish_run(args.run_id, status="complete")
    elif args.run_id and state in kaggle_backend.TERMINAL_BAD:
        ledger.finish_run(args.run_id, status="error", notes=state)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="gpu-router", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("quota", help="show remaining free quota per backend").set_defaults(func=cmd_quota)

    p = sub.add_parser("plan", help="show which backend a job would go to")
    p.add_argument("--kind", default="render")
    p.add_argument("--minutes", type=float, required=True, help="estimated job duration")
    p.add_argument("--tpu", action="store_true")
    p.add_argument("--cpu", action="store_true", help="job needs no accelerator")
    p.add_argument("--interactive", action="store_true", help="someone is waiting on it")
    p.add_argument("--personal", action="store_true", help="personal, non-commercial work (Kaggle's terms); without it Kaggle is refused")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("submit", help="route a job and push it")
    p.add_argument("job_dir", help="directory holding kernel-metadata.json and the notebook")
    p.add_argument("--kind", default="render")
    p.add_argument("--minutes", type=float, required=True)
    p.add_argument("--tpu", action="store_true")
    p.add_argument("--job-key", help="idempotency key; a repeat is refused")
    p.add_argument("--personal", action="store_true", help="personal, non-commercial work (Kaggle's terms); without it Kaggle is refused")
    p.add_argument("--timeout", type=int, help="cap the Kaggle session at this many seconds (-t)")
    p.add_argument("--wait", action="store_true")
    p.add_argument("--out", help="where to put fetched artifacts")
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("poll", help="check a pushed kernel")
    p.add_argument("ref", help="user/slug")
    p.add_argument("--run-id", type=int)
    p.set_defaults(func=cmd_poll)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
