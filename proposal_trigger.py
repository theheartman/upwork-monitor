"""
Bridges Agent 1 (scorer/alerts) and Agent 2 (proposal drafter).
Called from main.py immediately after a job alert is sent.
Errors are caught and logged — never crash the monitoring run.
"""

import logging
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "proposal-drafter"))

from strategy_router import select_strategy
from prompt_builder import SYSTEM_PROMPT, build_prompt
from api_client import generate_proposal, validate_proposal
from normalizer import Job
import alerts

logger = logging.getLogger(__name__)

TG_MAX = 4096


def generate_and_send(job: Job, signals: list[str]) -> None:
    """Generate a proposal draft and send it to Telegram. Swallows all exceptions."""
    try:
        _run(job, signals)
    except Exception as e:
        logger.warning(f"Proposal draft failed for {job.job_id}: {e}")


def _run(job: Job, signals: list[str]) -> None:
    strategy = select_strategy(signals)

    job_dict = {
        "title": job.title,
        "description": job.description,
        "hourly_min": job.hourly_min,
        "hourly_max": job.hourly_max,
        "fixed_amount": job.fixed_amount,
        "total_applicants": job.total_applicants,
    }

    user_prompt = build_prompt(job_dict, strategy)
    raw = generate_proposal(SYSTEM_PROMPT, user_prompt)

    cover_letter = _extract_section(raw, "COVER LETTER:", "SUGGESTED RATE:")
    suggested_rate = _extract_section(raw, "SUGGESTED RATE:", "STRATEGY NOTES:")

    validate_proposal(raw)  # logged server-side only

    text = (
        f"📝 Proposal Draft\n"
        f"💼 {job.title}\n\n"
        f"{cover_letter}"
    )
    if suggested_rate:
        text += f"\n\n💰 {suggested_rate}"

    if len(text) > TG_MAX:
        text = text[: TG_MAX - 3] + "..."

    alerts._send_message(text)
    logger.info(f"Proposal draft sent for {job.job_id}")


def _extract_section(text: str, start_marker: str, end_marker: str) -> str:
    """Pull text between two section markers, stripping the markers themselves."""
    pattern = re.compile(
        re.escape(start_marker) + r"\s*(.*?)\s*(?=" + re.escape(end_marker) + r"|$)",
        re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else text.strip()
