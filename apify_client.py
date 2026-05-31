import time
import requests
import logging
from config import APIFY_TOKEN, APIFY_ACTOR_ID, JOBS_PER_KEYWORD

logger = logging.getLogger(__name__)

APIFY_BASE = "https://api.apify.com/v2"
POLL_INTERVAL = 5       # seconds between status checks
POLL_TIMEOUT = 660      # 11 minutes max wait (actor timeout = 600s)
MAX_KEYWORDS_PER_RUN = 5  # actor hard limit


MAINTENANCE_RETRY_DELAY = 90   # seconds to wait after a maintenance failure
MAINTENANCE_MAX_RETRIES = 3


def run_actor(keywords: list[str], limit: int = JOBS_PER_KEYWORD) -> list[dict]:
    """Start Apify actor run(s), return combined raw items. Batches if >5 keywords."""
    if not APIFY_TOKEN or not APIFY_ACTOR_ID:
        raise ValueError("APIFY_TOKEN and APIFY_ACTOR_ID must be set in .env")

    batches = [keywords[i:i + MAX_KEYWORDS_PER_RUN]
               for i in range(0, len(keywords), MAX_KEYWORDS_PER_RUN)]

    all_items = []
    for batch in batches:
        items = _run_batch_with_retry(batch, limit)
        all_items.extend(items)

    logger.info(f"Total: {len(all_items)} items across {len(batches)} run(s)")
    return all_items


def _run_batch_with_retry(batch: list[str], limit: int) -> list[dict]:
    for attempt in range(1, MAINTENANCE_MAX_RETRIES + 1):
        run_id = _start_run(batch, limit)
        try:
            dataset_id = _wait_for_run(run_id)
            items = _download_dataset(dataset_id)
            logger.info(f"Actor run {run_id}: {len(items)} items for keywords {batch}")
            return items
        except RuntimeError as e:
            status_msg = _get_status_message(run_id)
            if "maintenance" in status_msg.lower() and attempt < MAINTENANCE_MAX_RETRIES:
                logger.warning(
                    f"Actor under maintenance (attempt {attempt}/{MAINTENANCE_MAX_RETRIES}). "
                    f"Retrying in {MAINTENANCE_RETRY_DELAY}s..."
                )
                time.sleep(MAINTENANCE_RETRY_DELAY)
            else:
                raise
    raise RuntimeError(f"Actor failed after {MAINTENANCE_MAX_RETRIES} attempts")


def _start_run(keywords: list[str], limit: int) -> str:
    resp = requests.post(
        f"{APIFY_BASE}/acts/{APIFY_ACTOR_ID}/runs",
        params={"token": APIFY_TOKEN, "memory": 512, "timeout": 600},
        json={"query": keywords, "limit": limit, "sort": "newest"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    run_id = data["data"]["id"]
    logger.info(f"Started actor run: {run_id}")
    return run_id


def _wait_for_run(run_id: str) -> str:
    """Poll until run succeeds or times out. Returns defaultDatasetId."""
    elapsed = 0
    while elapsed < POLL_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

        resp = requests.get(
            f"{APIFY_BASE}/actor-runs/{run_id}",
            params={"token": APIFY_TOKEN},
            timeout=30,
        )
        resp.raise_for_status()
        status_data = resp.json()["data"]
        status = status_data["status"]

        if status == "SUCCEEDED":
            return status_data["defaultDatasetId"]
        elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
            raise RuntimeError(f"Actor run {run_id} ended with status: {status}")

        logger.debug(f"Run {run_id} status: {status} ({elapsed}s elapsed)")

    raise TimeoutError(f"Actor run {run_id} did not complete within {POLL_TIMEOUT}s")


def _get_status_message(run_id: str) -> str:
    try:
        resp = requests.get(
            f"{APIFY_BASE}/actor-runs/{run_id}",
            params={"token": APIFY_TOKEN},
            timeout=10,
        )
        return resp.json().get("data", {}).get("statusMessage", "")
    except Exception:
        return ""


def _download_dataset(dataset_id: str) -> list[dict]:
    resp = requests.get(
        f"{APIFY_BASE}/datasets/{dataset_id}/items",
        params={"token": APIFY_TOKEN, "format": "json"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()
