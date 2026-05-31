"""
Proposal Drafter — Agents 2 → 3 → 4
Usage:
    python draft.py <job_id>                    # full pipeline: draft → critique → rewrite
    python draft.py --top                       # highest-scored job not yet applied
    python draft.py --tier APPLY_NOW            # all jobs of a tier from today
    python draft.py <job_id> --dry-run          # show strategy without calling API
    python draft.py <job_id> --raw              # Agent 2 only — skip critique and rewrite
    python draft.py <job_id> --critique-only    # Agent 2 + 3 — show critique, no rewrite
    python draft.py <job_id> --mark-applied     # mark job as applied in DB
    python draft.py <job_id> --outcome viewed   # record outcome (viewed/interviewed/hired/rejected)
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv

# Allow imports from the upwork-monitor parent directory
_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
sys.path.insert(0, _PARENT)
load_dotenv(os.path.join(_PARENT, ".env"))

from config import DB_PATH
from strategy_router import select_strategy
from prompt_builder import SYSTEM_PROMPT, build_prompt
from api_client import generate_proposal, validate_proposal
from critic import AGENT3_SYSTEM_PROMPT, build_critic_prompt
from rewriter import AGENT4_SYSTEM_PROMPT, build_rewriter_prompt
from validator import validate_final


DIVIDER = "═" * 60
VALID_OUTCOMES = {"viewed", "interviewed", "hired", "rejected"}


# ── Database helpers ──────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_job(job_id: str) -> Optional[dict]:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def load_top_job() -> Optional[dict]:
    """Highest-scored job not yet applied to."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE applied = 0 AND score > 0 ORDER BY score DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def load_tier_jobs(tier: str) -> list[dict]:
    """All jobs of a given tier seen today (UTC), not yet applied."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM jobs
               WHERE tier = ? AND applied = 0 AND score > 0
               AND first_seen_at LIKE ?
               ORDER BY score DESC""",
            (tier, f"{today}%"),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_applied(job_id: str) -> None:
    with _get_conn() as conn:
        conn.execute("UPDATE jobs SET applied = 1 WHERE job_id = ?", (job_id,))
    print(f"Marked {job_id} as applied.")


def set_outcome(job_id: str, outcome: str) -> None:
    with _get_conn() as conn:
        conn.execute("UPDATE jobs SET outcome = ? WHERE job_id = ?", (outcome, job_id))
    print(f"Outcome for {job_id} set to: {outcome}")


# ── Output helpers ────────────────────────────────────────────────────────────

def _format_budget(job: dict) -> str:
    h_min, h_max, fixed = job.get("hourly_min"), job.get("hourly_max"), job.get("fixed_amount")
    if h_min or h_max:
        parts = [f"${h_min:.0f}" if h_min else None,
                 f"${h_max:.0f}" if h_max else None]
        return "-".join(p for p in parts if p) + "/hr | HOURLY"
    elif fixed:
        return f"${fixed:,.0f} | FIXED"
    return "Budget not specified"


def _tier_emoji(tier: str) -> str:
    return {"APPLY_NOW": "🔴", "STRONG_FIT": "🟡", "MAYBE": "⚪", "SKIP": "❌"}.get(tier, "")


def print_job_header(job: dict) -> None:
    tier = job.get("tier", "")
    score = job.get("score", 0)
    apps = job.get("total_applicants")
    apps_str = f" | {apps} applicants" if apps is not None else ""
    print(DIVIDER)
    print(f" {_tier_emoji(tier)} {tier.replace('_', ' ')} — Score: {score}")
    print(f" {job['title']}")
    print(f" {_format_budget(job)}{apps_str}")
    print(DIVIDER)


def _copy_to_clipboard(text: str) -> bool:
    try:
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
        else:
            subprocess.run(["xclip", "-selection", "clipboard"],
                           input=text.encode(), check=True)
        return True
    except Exception:
        return False


def _extract_cover_letter(proposal_text: str) -> str:
    """Pull just the cover letter block for clipboard."""
    lines = proposal_text.splitlines()
    in_letter = False
    letter_lines = []
    for line in lines:
        if line.strip() == "COVER LETTER:":
            in_letter = True
            continue
        if in_letter and line.strip().startswith("SUGGESTED RATE:"):
            break
        if in_letter:
            letter_lines.append(line)
    return "\n".join(letter_lines).strip() if letter_lines else proposal_text


# ── Core flow ─────────────────────────────────────────────────────────────────

def draft_for_job(
    job: dict,
    dry_run: bool = False,
    raw: bool = False,
    critique_only: bool = False,
) -> None:
    signals = json.loads(job.get("signals") or "[]")
    strategy = select_strategy(signals)

    print_job_header(job)
    print(f"\n🔗 {job.get('link', '')}\n")

    if dry_run:
        print("── STRATEGY (dry run) ─────────────────────────────────────")
        print(f"  Primary angle : {strategy['primary_angle']}")
        print(f"  Tone          : {strategy['tone']}")
        print(f"  Risk reduction: {strategy['risk_reduction']}")
        print(f"  Depth signals : {', '.join(strategy['depth_signals']) or 'none'}")
        if strategy["proof_points"]:
            pp = strategy["proof_points"][0]
            print(f"  Case study    : {pp['case']}")
            print(f"  Metric        : {pp['metric']}")
        print()
        return

    # ── Agent 2: Draft ────────────────────────────────────────────────────────
    print("Agent 2: Drafting proposal...\n")
    user_prompt = build_prompt(job, strategy)
    draft = generate_proposal(SYSTEM_PROMPT, user_prompt)

    if raw:
        warnings = validate_proposal(draft, proof_points=strategy.get("proof_points"))
        if warnings:
            print("⚠️  Quality warnings:")
            for w in warnings:
                print(f"   {w}")
            print()
        print(draft)
        print()
        cover_letter = _extract_cover_letter(draft)
        if _copy_to_clipboard(cover_letter):
            print(DIVIDER)
            print(" 📋 Cover letter copied to clipboard (raw draft)")
            print(DIVIDER)
        return

    # ── Agent 3: Critique ─────────────────────────────────────────────────────
    print("Agent 3: Critiquing...\n")
    critic_prompt = build_critic_prompt(draft, job, strategy)
    critique = generate_proposal(AGENT3_SYSTEM_PROMPT, critic_prompt)

    print("── CRITIQUE ───────────────────────────────────────────────")
    print(critique)
    print()

    if critique_only:
        print("── RAW DRAFT (for reference) ──────────────────────────────")
        print(draft)
        return

    # Skip rewrite if critic said PASS
    verdict_line = next(
        (l for l in critique.splitlines() if l.startswith("VERDICT:")), ""
    )
    verdict = verdict_line.replace("VERDICT:", "").strip()

    if verdict == "PASS":
        print("Agent 3 verdict: PASS — skipping rewrite.\n")
        final = draft
    elif verdict == "REJECT":
        print("Agent 3 verdict: REJECT — proposal is off-target. Review critique above.")
        return
    else:
        # ── Agent 4: Rewrite ──────────────────────────────────────────────────
        print("Agent 4: Rewriting...\n")
        rewriter_prompt = build_rewriter_prompt(draft, critique, job, strategy)
        final = generate_proposal(AGENT4_SYSTEM_PROMPT, rewriter_prompt)

    # ── Post-rewrite validation ───────────────────────────────────────────────
    issues = validate_final(final, proof_points=strategy.get("proof_points"))
    if issues:
        print("⚠️  Post-rewrite validation issues:")
        for issue in issues:
            print(f"   {issue}")
        print()

    print("── FINAL PROPOSAL ─────────────────────────────────────────")
    print(final)
    print()

    cover_letter = _extract_cover_letter(final)
    if _copy_to_clipboard(cover_letter):
        print(DIVIDER)
        print(" 📋 Cover letter copied to clipboard")
        print(DIVIDER)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Upwork Proposal Drafter")
    parser.add_argument("job_id", nargs="?", help="Job ID from Agent 1 database")
    parser.add_argument("--top", action="store_true", help="Use highest-scored unapplied job")
    parser.add_argument("--tier", help="Generate for all jobs of this tier today (APPLY_NOW, STRONG_FIT, etc.)")
    parser.add_argument("--dry-run", action="store_true", help="Show strategy without calling API")
    parser.add_argument("--raw", action="store_true", help="Agent 2 only — skip critique and rewrite")
    parser.add_argument("--critique-only", action="store_true", help="Agent 2 + 3 — show critique without rewriting")
    parser.add_argument("--mark-applied", action="store_true", help="Mark job as applied")
    parser.add_argument("--outcome", choices=VALID_OUTCOMES, help="Record outcome for a job")
    args = parser.parse_args()

    if args.mark_applied:
        if not args.job_id:
            parser.error("--mark-applied requires a job_id")
        mark_applied(args.job_id)
        return

    if args.outcome:
        if not args.job_id:
            parser.error("--outcome requires a job_id")
        set_outcome(args.job_id, args.outcome)
        return

    kwargs = dict(
        dry_run=args.dry_run,
        raw=args.raw,
        critique_only=args.critique_only,
    )

    if args.top:
        job = load_top_job()
        if not job:
            print("No unapplied jobs found.")
            return
        draft_for_job(job, **kwargs)

    elif args.tier:
        jobs = load_tier_jobs(args.tier.upper())
        if not jobs:
            print(f"No unapplied {args.tier.upper()} jobs found today.")
            return
        for job in jobs:
            draft_for_job(job, **kwargs)
            if len(jobs) > 1:
                input("\nPress Enter for next job...")

    elif args.job_id:
        job = load_job(args.job_id)
        if not job:
            print(f"Job not found: {args.job_id}")
            return
        draft_for_job(job, **kwargs)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
