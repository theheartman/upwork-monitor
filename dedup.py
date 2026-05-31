import json
import sqlite3
import logging
from datetime import datetime, timezone
from normalizer import Job
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                title TEXT,
                link TEXT,
                description TEXT,
                score INTEGER,
                tier TEXT,
                signals TEXT,
                search_keyword TEXT,
                job_type TEXT,
                hourly_min REAL,
                hourly_max REAL,
                fixed_amount REAL,
                total_applicants INTEGER,
                client_country TEXT,
                client_total_spent REAL,
                data_type TEXT,
                posted_on TEXT,
                first_seen_at TEXT,
                alerted INTEGER DEFAULT 0,
                applied INTEGER DEFAULT 0,
                outcome TEXT,
                qualified_countries TEXT
            );

            CREATE TABLE IF NOT EXISTS run_log (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT,
                completed_at TEXT,
                total_jobs_fetched INTEGER,
                new_jobs INTEGER,
                alerted_jobs INTEGER,
                keywords TEXT,
                keyword_stats TEXT
            );
        """)
    # Migrations
    with get_conn() as conn:
        run_cols = [r[1] for r in conn.execute("PRAGMA table_info(run_log)").fetchall()]
        if "keyword_stats" not in run_cols:
            conn.execute("ALTER TABLE run_log ADD COLUMN keyword_stats TEXT")
        job_cols = [r[1] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()]
        if "qualified_countries" not in job_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN qualified_countries TEXT")
    logger.info("Database initialized")


def is_new(job_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return row is None


def insert_job(job: Job, score: int, tier: str, signals: list[str]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO jobs (
                job_id, title, link, description, score, tier, signals,
                search_keyword, job_type, hourly_min, hourly_max, fixed_amount,
                total_applicants, client_country, client_total_spent,
                data_type, posted_on, first_seen_at, qualified_countries
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.job_id, job.title, job.link, job.description,
                score, tier, json.dumps(signals),
                job.search_keyword, job.job_type,
                job.hourly_min, job.hourly_max, job.fixed_amount,
                job.total_applicants, job.client_country, job.client_total_spent,
                job.data_type, job.posted_on,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(job.qualified_countries) if job.qualified_countries else None,
            ),
        )


def update_applicants(job_id: str, total_applicants: int) -> None:
    """Update applicant count if the new value is higher (competition tracking)."""
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE jobs SET total_applicants = ?
            WHERE job_id = ? AND (total_applicants IS NULL OR total_applicants < ?)
            """,
            (total_applicants, job_id, total_applicants),
        )


def mark_alerted(job_id: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE jobs SET alerted = 1 WHERE job_id = ?", (job_id,))


def log_run(started_at: str, total_fetched: int, new_jobs: int,
            alerted_jobs: int, keywords: list[str],
            keyword_stats=None) -> None:
    completed_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO run_log (started_at, completed_at, total_jobs_fetched,
                                 new_jobs, alerted_jobs, keywords, keyword_stats)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (started_at, completed_at, total_fetched, new_jobs,
             alerted_jobs, json.dumps(keywords),
             json.dumps(keyword_stats) if keyword_stats else None),
        )


def get_daily_stats(date_str: str) -> dict:
    """Return counts per tier for a given date (YYYY-MM-DD)."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT tier, COUNT(*) as cnt
            FROM jobs
            WHERE first_seen_at LIKE ?
            GROUP BY tier
            """,
            (f"{date_str}%",),
        ).fetchall()

        totals = conn.execute(
            "SELECT COUNT(*) as total, SUM(alerted) as alerted FROM jobs WHERE first_seen_at LIKE ?",
            (f"{date_str}%",),
        ).fetchone()

        run_stats = conn.execute(
            """
            SELECT SUM(total_jobs_fetched) as scanned, SUM(new_jobs) as new_jobs, COUNT(*) as runs
            FROM run_log WHERE started_at LIKE ?
            """,
            (f"{date_str}%",),
        ).fetchone()

        tier_counts = {r["tier"]: r["cnt"] for r in rows}
        top_job = conn.execute(
            """
            SELECT title, hourly_min, hourly_max, fixed_amount, score
            FROM jobs WHERE first_seen_at LIKE ?
            ORDER BY score DESC LIMIT 1
            """,
            (f"{date_str}%",),
        ).fetchone()

    return {
        "tier_counts": tier_counts,
        "total_new": (totals["total"] or 0) if totals else 0,
        "total_alerted": (totals["alerted"] or 0) if totals else 0,
        "scanned": (run_stats["scanned"] or 0) if run_stats else 0,
        "new_jobs": (run_stats["new_jobs"] or 0) if run_stats else 0,
        "runs": (run_stats["runs"] or 0) if run_stats else 0,
        "top_job": dict(top_job) if top_job else None,
    }
