from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Job:
    # Identity
    job_id: str
    title: str
    link: str
    search_keyword: str

    # Content
    description: str
    skills: list[str]
    category: str
    tier: str

    # Budget
    job_type: str
    hourly_min: Optional[float]
    hourly_max: Optional[float]
    fixed_amount: Optional[float]

    # Client Activity (None if private)
    total_applicants: Optional[int]
    invitations_sent: Optional[int]
    total_invited_to_interview: Optional[int]
    total_hired: Optional[int]
    last_buyer_activity: Optional[str]

    # Client Profile
    client_country: Optional[str]
    client_score: Optional[float]
    client_total_spent: Optional[float]
    client_total_hires: Optional[int]
    payment_verified: Optional[bool]
    client_open_jobs: Optional[int]

    # Qualifications
    min_jss_required: Optional[float]

    # Metadata
    data_type: str          # "detail" or "private"
    posted_on: Optional[str]
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    qualified_countries: list = field(default_factory=list)


def normalize(raw: dict, search_keyword: str = "") -> Job:
    """Convert raw Apify item to Job dataclass."""
    data_type = raw.get("type", "detail")
    if data_type not in ("detail", "private"):
        data_type = "detail"

    # Use actor-provided search keyword if not overridden
    if not search_keyword:
        search_keyword = raw.get("related_search", "") or ""

    link = _str(raw, "link", "")
    job_id = _extract_job_id(raw, link)

    title = (
        _str(raw, "title")
        or _nested(raw, "data", "opening", "info", "title")
        or _nested(raw, "data", "title")
        or ""
    )

    description = (
        _nested(raw, "data", "opening", "description")
        or _nested(raw, "data", "description")
        or ""
    )

    skills = _extract_skills(raw)
    category = _nested(raw, "data", "opening", "category", "name") or ""
    tier = (
        _nested(raw, "data", "opening", "contractorTier")
        or _nested(raw, "data", "jobTile", "job", "contractorTier")
        or ""
    )

    job_type = (
        _nested(raw, "data", "opening", "info", "type")
        or _nested(raw, "data", "jobTile", "job", "jobType")
        or ""
    ).upper()

    hourly_min = _float_val(
        _nested(raw, "data", "opening", "extendedBudgetInfo", "hourlyBudgetMin")
        or _nested(raw, "data", "jobTile", "job", "hourlyBudgetMin")
    )
    hourly_max = _float_val(
        _nested(raw, "data", "opening", "extendedBudgetInfo", "hourlyBudgetMax")
        or _nested(raw, "data", "jobTile", "job", "hourlyBudgetMax")
    )
    fixed_amount = _float_val(
        _nested(raw, "data", "opening", "budget", "amount")
        or _nested(raw, "data", "jobTile", "job", "fixedPriceAmount", "amount")
    )

    activity = _nested(raw, "data", "opening", "clientActivity") or {}
    total_applicants = _int_val(activity.get("totalApplicants"))
    invitations_sent = _int_val(activity.get("invitationsSent"))
    total_invited_to_interview = _int_val(activity.get("totalInvitedToInterview"))
    total_hired = _int_val(activity.get("totalHired"))
    last_buyer_activity = _str(activity, "lastBuyerActivity")

    buyer = _nested(raw, "data", "buyer") or {}
    buyer_stats = buyer.get("stats", {}) or {}
    buyer_jobs = buyer.get("jobs", {}) or {}

    client_country = (
        _nested(raw, "data", "opening", "clientCountry")
        or _nested(buyer, "location", "country")
        or None
    )
    client_score = _float_val(_nested(buyer_stats, "totalFeedback"))
    client_total_spent = _float_val(_nested(buyer_stats, "totalCharges", "amount"))
    client_total_hires = _int_val(buyer_stats.get("totalJobsWithHires"))
    payment_verified = bool(buyer.get("isPaymentMethodVerified")) if "isPaymentMethodVerified" in buyer else None
    client_open_jobs = _int_val(buyer_jobs.get("openCount"))

    min_jss_required = _float_val(
        _nested(raw, "data", "opening", "qualifications", "minRisingTalentScore")
        or _nested(raw, "data", "opening", "qualifications", "minJobSuccessScore")
    )

    qualified_countries = []
    quals = _nested(raw, "data", "qualifications") or {}
    countries_raw = quals.get("countries", []) or []
    if isinstance(countries_raw, list):
        for item in countries_raw:
            if isinstance(item, str) and item.strip():
                qualified_countries.append(item.strip())
            elif isinstance(item, dict):
                name = item.get("name", "")
                if name:
                    qualified_countries.append(name)
    elif isinstance(countries_raw, dict):
        for i in range(20):
            val = countries_raw.get(str(i))
            if val and isinstance(val, str):
                qualified_countries.append(val.strip())

    posted_on = (
        _nested(raw, "data", "opening", "info", "createdOn")
        or _nested(raw, "data", "jobTile", "job", "createdOn")
        or None
    )

    return Job(
        job_id=job_id,
        title=title,
        link=link,
        search_keyword=search_keyword,
        description=description,
        skills=skills,
        category=category,
        tier=tier,
        job_type=job_type,
        hourly_min=hourly_min,
        hourly_max=hourly_max,
        fixed_amount=fixed_amount,
        total_applicants=total_applicants,
        invitations_sent=invitations_sent,
        total_invited_to_interview=total_invited_to_interview,
        total_hired=total_hired,
        last_buyer_activity=last_buyer_activity,
        client_country=client_country,
        client_score=client_score,
        client_total_spent=client_total_spent,
        client_total_hires=client_total_hires,
        payment_verified=payment_verified,
        client_open_jobs=client_open_jobs,
        min_jss_required=min_jss_required,
        data_type=data_type,
        posted_on=posted_on,
        qualified_countries=qualified_countries,
    )


def normalize_batch(items: list[dict], search_keyword: str = "") -> list[Job]:
    jobs = []
    for item in items:
        try:
            jobs.append(normalize(item, search_keyword))
        except Exception:
            pass
    return jobs


# ── helpers ──────────────────────────────────────────────────────────────────

def _extract_job_id(raw: dict, link: str) -> str:
    if link:
        return link
    return (
        _nested(raw, "data", "opening", "info", "id")
        or _nested(raw, "data", "id")
        or str(id(raw))
    )


def _extract_skills(raw: dict) -> list[str]:
    skills = []
    data = raw.get("data", {}) or {}

    # Primary location: data.sandsData.ontologySkills (list)
    sands = data.get("sandsData", {}) or {}
    onto = sands.get("ontologySkills", []) or []
    if isinstance(onto, list):
        for item in onto:
            if isinstance(item, dict):
                label = item.get("prefLabel", "")
                if label and label not in skills:
                    skills.append(label)

    # Fallback: data.ontologySkills (list or numbered keys)
    onto2 = data.get("ontologySkills", []) or []
    if isinstance(onto2, list):
        for item in onto2:
            if isinstance(item, dict):
                label = item.get("prefLabel", "")
                if label and label not in skills:
                    skills.append(label)
    elif isinstance(onto2, dict):
        for i in range(20):
            val = _nested(onto2, str(i), "prefLabel")
            if val and val not in skills:
                skills.append(val)

    return skills


def _nested(obj: dict, *keys):
    """Traverse nested dict by path segments. Supports 'a/b/c' as a single key too."""
    cur = obj
    for key in keys:
        if cur is None:
            return None
        if isinstance(cur, dict):
            # Try slash-separated key first (Apify flattened format)
            if "/" in str(key):
                parts = str(key).split("/")
                for part in parts:
                    cur = cur.get(part) if isinstance(cur, dict) else None
            else:
                cur = cur.get(str(key))
        else:
            return None
    return cur


def _str(obj: dict, key: str, default: str = "") -> str:
    val = obj.get(key)
    return str(val) if val is not None else default


def _float_val(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _int_val(val) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None
