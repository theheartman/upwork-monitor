"""
Skill: draft_proposal

Генерирует proposal для вакансии из БД через пайплайн Agent 2 → 3 → 4.

Usage:
    python skills/draft_proposal.py <job_id>              # полный пайплайн
    python skills/draft_proposal.py --top                 # топ-1 по score среди не поданных
    python skills/draft_proposal.py --tier APPLY_NOW      # все APPLY_NOW за сегодня
    python skills/draft_proposal.py <job_id> --dry-run    # показать стратегию без API
    python skills/draft_proposal.py <job_id> --raw        # только Agent 2, без critique
    python skills/draft_proposal.py <job_id> --critique-only  # Agent 2 + 3, без rewrite
    python skills/draft_proposal.py <job_id> --mark-applied   # отметить как поданную
    python skills/draft_proposal.py <job_id> --outcome hired  # записать исход
"""

import argparse
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_DRAFTER = os.path.join(_ROOT, "proposal-drafter")

sys.path.insert(0, _ROOT)
sys.path.insert(0, _DRAFTER)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

from draft import (
    load_job,
    load_top_job,
    load_tier_jobs,
    draft_for_job,
    mark_applied,
    set_outcome,
    VALID_OUTCOMES,
)


def run(
    job_id=None,
    top=False,
    tier=None,
    dry_run=False,
    raw=False,
    critique_only=False,
    mark_applied_flag=False,
    outcome=None,
):
    kwargs = dict(dry_run=dry_run, raw=raw, critique_only=critique_only)

    if mark_applied_flag:
        if not job_id:
            raise ValueError("--mark-applied requires a job_id")
        mark_applied(job_id)
        return {"action": "mark_applied", "job_id": job_id}

    if outcome:
        if not job_id:
            raise ValueError("--outcome requires a job_id")
        set_outcome(job_id, outcome)
        return {"action": "set_outcome", "job_id": job_id, "outcome": outcome}

    if top:
        job = load_top_job()
        if not job:
            print("No unapplied jobs found.")
            return {"drafted": 0}
        draft_for_job(job, **kwargs)
        return {"drafted": 1, "job_id": job["job_id"], "score": job["score"]}

    if tier:
        jobs = load_tier_jobs(tier.upper())
        if not jobs:
            print(f"No unapplied {tier.upper()} jobs found today.")
            return {"drafted": 0}
        for i, job in enumerate(jobs):
            draft_for_job(job, **kwargs)
            if i < len(jobs) - 1:
                input("\nPress Enter for next job...")
        return {"drafted": len(jobs), "tier": tier.upper()}

    if job_id:
        job = load_job(job_id)
        if not job:
            print(f"Job not found: {job_id}")
            return {"drafted": 0}
        draft_for_job(job, **kwargs)
        return {"drafted": 1, "job_id": job_id, "score": job["score"]}

    raise ValueError("Provide job_id, --top, or --tier")


def main():
    parser = argparse.ArgumentParser(description="Skill: Proposal Drafter")
    parser.add_argument("job_id", nargs="?", help="Job ID из БД Agent 1")
    parser.add_argument("--top", action="store_true", help="Топ-1 по score среди не поданных")
    parser.add_argument("--tier", help="Все вакансии тира за сегодня (APPLY_NOW, STRONG_FIT...)")
    parser.add_argument("--dry-run", action="store_true", help="Показать стратегию без API-вызова")
    parser.add_argument("--raw", action="store_true", help="Только Agent 2, без critique/rewrite")
    parser.add_argument("--critique-only", action="store_true", help="Agent 2 + 3, без rewrite")
    parser.add_argument("--mark-applied", action="store_true", help="Отметить вакансию как поданную")
    parser.add_argument("--outcome", choices=VALID_OUTCOMES, help="Записать исход вакансии")
    args = parser.parse_args()

    run(
        job_id=args.job_id,
        top=args.top,
        tier=args.tier,
        dry_run=args.dry_run,
        raw=args.raw,
        critique_only=args.critique_only,
        mark_applied_flag=args.mark_applied,
        outcome=args.outcome,
    )


if __name__ == "__main__":
    main()
