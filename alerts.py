import logging
import requests
from normalizer import Job
from scorer import get_tier, tier_emoji
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SCORE_APPLY_NOW

logger = logging.getLogger(__name__)

TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
MAX_DESC_LONG = 200
MAX_DESC_SHORT = 150


def send_job_alert(job: Job, score: int, signals: list[str]) -> bool:
    """Send job alert to Telegram. Returns True if sent."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials not set — skipping alert")
        return False

    tier = get_tier(score)
    emoji = tier_emoji(tier)
    label = tier.replace("_", " ")

    desc_len = MAX_DESC_LONG if score >= SCORE_APPLY_NOW else MAX_DESC_SHORT
    desc_preview = (job.description or "")[:desc_len].strip()
    if len(job.description or "") > desc_len:
        desc_preview += "..."

    budget_str = _format_budget(job)
    applicants_str = f"👥 {job.total_applicants} applicants | " if job.total_applicants is not None else ""
    tier_str = f"🏷 {job.tier}" if job.tier else ""
    country_str = f"🌍 {job.client_country}" if job.client_country else ""
    spent_str = f"💳 ${job.client_total_spent:,.0f} spent" if job.client_total_spent else ""

    client_line = " | ".join(filter(None, [country_str, spent_str]))

    signals_block = "\n".join(f"• {s}" for s in signals if not s.startswith("FILTERED"))

    private_warning = ""
    if job.data_type == "private":
        private_warning = "\n⚠️ Private listing — open in browser to see full details"

    text = (
        f"{emoji} {label} — Score: {score}/100\n"
        f"\n"
        f"💼 {job.title}\n"
        f"💰 {budget_str}\n"
    )
    if applicants_str or tier_str:
        text += f"{applicants_str}{tier_str}\n"
    if client_line:
        text += f"{client_line}\n"

    text += (
        f"\n📊 Signals:\n{signals_block}\n"
        f"\n📝 \"{desc_preview}\"\n"
        f"{private_warning}\n"
        f"\n🔗 {job.link}"
    )

    return _send_message(text)


def send_run_summary(stats: dict) -> bool:
    """Send per-run summary immediately after a run completes."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    tier_counts = stats.get("tier_counts", {})
    top = stats.get("top_job")
    top_line = ""
    if top:
        budget = _format_budget_raw(top.get("hourly_min"), top.get("hourly_max"), top.get("fixed_amount"))
        top_line = f"\nTop: {top['title'][:55]} — {budget} — Score: {top['score']}"

    text = (
        f"📊 Run complete\n"
        f"Scanned: {stats.get('scanned', 0)} | New: {stats.get('new_jobs', 0)} | Alerted: {stats.get('alerted', 0)}\n"
        f"🔴 {tier_counts.get('APPLY_NOW', 0)}  "
        f"🟡 {tier_counts.get('STRONG_FIT', 0)}  "
        f"⚪ {tier_counts.get('MAYBE', 0)}  "
        f"❌ {tier_counts.get('SKIP', 0)}"
        f"{top_line}"
    )

    return _send_message(text)


def send_error_alert(message: str) -> None:
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        _send_message(f"⚠️ Upwork Monitor Error:\n{message}")


def _send_message(text: str) -> bool:
    try:
        resp = requests.post(
            f"{TG_API}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        if not resp.ok:
            logger.error(f"Telegram error {resp.status_code}: {resp.text}")
            return False
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def _format_budget(job: Job) -> str:
    return _format_budget_raw(job.hourly_min, job.hourly_max, job.fixed_amount)


def _format_budget_raw(hourly_min, hourly_max, fixed_amount) -> str:
    if hourly_min or hourly_max:
        parts = [f"${hourly_min:.0f}" if hourly_min else None,
                 f"${hourly_max:.0f}" if hourly_max else None]
        rate = "-".join(filter(None, parts))
        return f"{rate}/hr | HOURLY"
    elif fixed_amount:
        return f"${fixed_amount:,.0f} | FIXED"
    return "Budget not specified"
