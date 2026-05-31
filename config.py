import os
from dotenv import load_dotenv

load_dotenv()

# Apify
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
APIFY_ACTOR_ID = os.getenv("APIFY_ACTOR_ID", "")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Scoring thresholds
SCORE_APPLY_NOW = int(os.getenv("SCORE_APPLY_NOW", "80"))
SCORE_STRONG_FIT = int(os.getenv("SCORE_STRONG_FIT", "60"))

# Scheduling (CET/Europe/Warsaw)
RUN_TIMES = os.getenv("RUN_TIMES", "07:30,15:00").split(",")
DIGEST_TIME = os.getenv("DIGEST_TIME", "22:00")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Warsaw")

# Database
DB_PATH = os.path.join(os.path.dirname(__file__), "db", "jobs.db")

# Search keywords
PRIMARY_KEYWORDS = [
    "Clay enrichment",
    "Clay CRM",
    "GTM engineer",
    "RevOps automation",
]

SECONDARY_KEYWORDS = [
    "CRM automation specialist",
    "Clay automation",
    "HubSpot automation consultant",
    "outbound enrichment",
    "sales automation architect",
    "CRM data cleanup",
    "lead generation automation",
]

ALL_KEYWORDS = PRIMARY_KEYWORDS + SECONDARY_KEYWORDS

JOBS_PER_KEYWORD = int(os.getenv("JOBS_PER_KEYWORD", "200"))
JOBS_PER_KEYWORD_SECONDARY = int(os.getenv("JOBS_PER_KEYWORD_SECONDARY", "75"))
