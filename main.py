"""
Upwork Premium Job Monitor
Usage:
    python main.py          # daemon mode (scheduled runs)
    python main.py --once   # single run and exit
    python main.py --digest # send daily digest and exit
"""

import argparse
import logging
import time
from datetime import datetime, timezone

import pytz

import apify_client
import dedup
import alerts
# import proposal_trigger
from normalizer import normalize_batch
from scorer import score_job, get_tier
from config import (
    PRIMARY_KEYWORDS, SECONDARY_KEYWORDS, ALL_KEYWORDS,
    RUN_TIMES, TIMEZONE, SCORE_STRONG_FIT,
    JOBS_PER_KEYWORD, JOBS_PER_KEYWORD_SECONDARY,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


def run_once() -> dict:
    """One full fetch → score → alert cycle. Returns run stats."""
    started_at = datetime.now(timezone.utc).isoformat()
    logger.info(f"Starting run — {len(PRIMARY_KEYWORDS)} primary, {len(SECONDARY_KEYWORDS)} secondary keywords")

    # Fetch primary keywords at full limit, secondary at reduced limit
    raw_items = apify_client.run_actor(PRIMARY_KEYWORDS, limit=JOBS_PER_KEYWORD)
    raw_items += apify_client.run_actor(SECONDARY_KEYWORDS, limit=JOBS_PER_KEYWORD_SECONDARY)
    jobs = normalize_batch(raw_items)
    logger.info(f"Normalized {len(jobs)} jobs")

    # Count per keyword before dedup
    keyword_stats = {}
    for job in jobs:
        kw = job.search_keyword or "unknown"
        keyword_stats[kw] = keyword_stats.get(kw, 0) + 1
    logger.info("Pre-dedup keyword counts: " + ", ".join(f"{k}: {v}" for k, v in sorted(keyword_stats.items(), key=lambda x: -x[1])))

    new_count = 0
    alerted_count = 0
    tier_counts = {"APPLY_NOW": 0, "STRONG_FIT": 0, "MAYBE": 0, "SKIP": 0}
    top_job = None

    for job in jobs:
        # Dedup: update applicants if seen before, skip scoring
        if not dedup.is_new(job.job_id):
            if job.total_applicants is not None:
                dedup.update_applicants(job.job_id, job.total_applicants)
            continue

        # Score
        score, signals = score_job(job)
        tier = get_tier(score)

        # Store
        dedup.insert_job(job, score, tier, signals)
        new_count += 1
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

        if top_job is None or score > top_job["score"]:
            top_job = {
                "title": job.title,
                "score": score,
                "hourly_min": job.hourly_min,
                "hourly_max": job.hourly_max,
                "fixed_amount": job.fixed_amount,
            }

        logger.info(f"[{score:3d}] {tier:10s} — {job.title[:60]}")

        # Alert if above threshold
        if score >= SCORE_STRONG_FIT:
            sent = alerts.send_job_alert(job, score, signals)
            if sent:
                dedup.mark_alerted(job.job_id)
                alerted_count += 1
                # proposal_trigger.generate_and_send(job, signals)

    dedup.log_run(started_at, len(raw_items), new_count, alerted_count, ALL_KEYWORDS, keyword_stats)
    logger.info(f"Run complete — {new_count} new jobs, {alerted_count} alerts sent")

    alerts.send_run_summary({
        "scanned": len(raw_items),
        "new_jobs": new_count,
        "alerted": alerted_count,
        "tier_counts": tier_counts,
        "top_job": top_job,
    })

    return {"total_fetched": len(raw_items), "new": new_count, "alerted": alerted_count}


def send_digest() -> None:
    tz = pytz.timezone(TIMEZONE)
    # Display label uses local timezone; DB query uses UTC (matches first_seen_at storage)
    date_label = datetime.now(tz).strftime("%B %d, %Y")
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stats = dedup.get_daily_stats(today_utc)
    alerts.send_daily_digest(date_label, stats)
    logger.info(f"Daily digest sent for {today_utc} (UTC)")


def run_daemon() -> None:
    """Block forever, running on RUN_TIMES schedule."""
    tz = pytz.timezone(TIMEZONE)
    logger.info(f"Daemon started. Schedule: {RUN_TIMES} ({TIMEZONE})")

    last_run_minute: str = ""  # "HH:MM" of last executed slot

    while True:
        now = datetime.now(tz)
        current_hhmm = now.strftime("%H:%M")

        if current_hhmm != last_run_minute and current_hhmm in RUN_TIMES:
            last_run_minute = current_hhmm
            try:
                run_once()
            except Exception as e:
                logger.error(f"Run failed: {e}", exc_info=True)
                alerts.send_error_alert(str(e))

        time.sleep(30)


def main() -> None:
    parser = argparse.ArgumentParser(description="Upwork Premium Job Monitor")
    parser.add_argument("--once", action="store_true", help="Single run and exit")
    parser.add_argument("--digest", action="store_true", help="Send daily digest and exit")
    args = parser.parse_args()

    dedup.init_db()

    if args.once:
        run_once()
    elif args.digest:
        send_digest()
    else:
        run_daemon()


if __name__ == "__main__":
    main()
