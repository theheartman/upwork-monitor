"""
Skill: upwork_job_search

Запускает поиск вакансий на Upwork, оценивает релевантность и сохраняет в БД.

Usage:
    python skills/upwork_job_search.py                        # прогон с keywords из config.py
    python skills/upwork_job_search.py --keywords "Clay CRM" "GTM engineer"
    python skills/upwork_job_search.py --primary-only
    python skills/upwork_job_search.py --secondary-only
    python skills/upwork_job_search.py --limit 50
    python skills/upwork_job_search.py --no-alerts            # без Telegram
    python skills/upwork_job_search.py --dry-run              # score без записи в БД
"""

import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import apify_client
import dedup
import alerts
from normalizer import normalize_batch
from scorer import score_job, get_tier
from config import (
    PRIMARY_KEYWORDS, SECONDARY_KEYWORDS, ALL_KEYWORDS,
    SCORE_STRONG_FIT, JOBS_PER_KEYWORD, JOBS_PER_KEYWORD_SECONDARY,
)
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("upwork_job_search")


def run(
    keywords=None,
    limit=None,
    primary_only=False,
    secondary_only=False,
    no_alerts=False,
    dry_run=False,
):
    dedup.init_db()
    started_at = datetime.now(timezone.utc).isoformat()

    # Определяем набор ключевых слов
    if keywords:
        primary = keywords
        secondary = []
        primary_limit = limit or JOBS_PER_KEYWORD
        secondary_limit = 0
    elif primary_only:
        primary = PRIMARY_KEYWORDS
        secondary = []
        primary_limit = limit or JOBS_PER_KEYWORD
        secondary_limit = 0
    elif secondary_only:
        primary = []
        secondary = SECONDARY_KEYWORDS
        primary_limit = 0
        secondary_limit = limit or JOBS_PER_KEYWORD_SECONDARY
    else:
        primary = PRIMARY_KEYWORDS
        secondary = SECONDARY_KEYWORDS
        primary_limit = limit or JOBS_PER_KEYWORD
        secondary_limit = limit or JOBS_PER_KEYWORD_SECONDARY

    logger.info(f"Keywords: {len(primary)} primary, {len(secondary)} secondary — dry_run={dry_run}")

    raw_items = []
    if primary:
        raw_items += apify_client.run_actor(primary, limit=primary_limit)
    if secondary:
        raw_items += apify_client.run_actor(secondary, limit=secondary_limit)

    jobs = normalize_batch(raw_items)
    logger.info(f"Fetched {len(raw_items)} raw items → {len(jobs)} normalized")

    keyword_stats = {}
    for job in jobs:
        kw = job.search_keyword or "unknown"
        keyword_stats[kw] = keyword_stats.get(kw, 0) + 1

    new_count = 0
    alerted_count = 0
    tier_counts = {"APPLY_NOW": 0, "STRONG_FIT": 0, "MAYBE": 0, "SKIP": 0}
    top_job = None

    for job in jobs:
        if not dry_run and not dedup.is_new(job.job_id):
            if job.total_applicants is not None:
                dedup.update_applicants(job.job_id, job.total_applicants)
            continue

        score, signals = score_job(job)
        tier = get_tier(score)

        if not dry_run:
            dedup.insert_job(job, score, tier, signals)

        new_count += 1
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

        if top_job is None or score > top_job["score"]:
            top_job = {"title": job.title, "score": score}

        logger.info(f"[{score:3d}] {tier:10s} — {job.title[:60]}")

        if not no_alerts and not dry_run and score >= SCORE_STRONG_FIT:
            sent = alerts.send_job_alert(job, score, signals)
            if sent:
                dedup.mark_alerted(job.job_id)
                alerted_count += 1

    if not dry_run:
        used_keywords = (primary + secondary) or ALL_KEYWORDS
        dedup.log_run(started_at, len(raw_items), new_count, alerted_count, used_keywords, keyword_stats)
        if not no_alerts:
            alerts.send_run_summary({
                "scanned": len(raw_items),
                "new_jobs": new_count,
                "alerted": alerted_count,
                "tier_counts": tier_counts,
                "top_job": top_job,
            })

    logger.info(f"Done — {new_count} new, {alerted_count} alerted | tiers: {tier_counts}")
    return {"fetched": len(raw_items), "new": new_count, "alerted": alerted_count, "tiers": tier_counts}


def main():
    parser = argparse.ArgumentParser(description="Skill: Upwork Job Search")
    parser.add_argument("--keywords", nargs="+", help="Кастомные ключевые слова (заменяют config.py)")
    parser.add_argument("--limit", type=int, help="Лимит вакансий на ключевое слово")
    parser.add_argument("--primary-only", action="store_true", help="Только primary keywords")
    parser.add_argument("--secondary-only", action="store_true", help="Только secondary keywords")
    parser.add_argument("--no-alerts", action="store_true", help="Не отправлять Telegram-уведомления")
    parser.add_argument("--dry-run", action="store_true", help="Score без записи в БД и без алертов")
    args = parser.parse_args()

    run(
        keywords=args.keywords,
        limit=args.limit,
        primary_only=args.primary_only,
        secondary_only=args.secondary_only,
        no_alerts=args.no_alerts,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
