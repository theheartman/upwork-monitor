import re
from datetime import datetime, timezone
from normalizer import Job


def score_job(job: Job) -> tuple[int, list[str]]:
    """Returns (score 0-100, list of triggered signal labels)."""
    score = 0
    signals: list[str] = []

    full_text = f"{job.title} {job.description} {' '.join(job.skills)}".lower()

    # ── 1. Budget Gate (hard filter + 15-20 pts) ─────────────────────────────
    meets_budget = False
    if job.hourly_max and job.hourly_max >= 50:
        meets_budget = True
    elif job.hourly_min and job.hourly_min >= 50:
        meets_budget = True
    elif job.fixed_amount and job.fixed_amount > 300:
        meets_budget = True

    if not meets_budget:
        return (0, ["FILTERED: Below budget threshold"])

    if job.hourly_max and job.hourly_max >= 100:
        score += 20; signals.append(f"ELITE_RATE: ${job.hourly_max}/hr")
    elif job.hourly_max and job.hourly_max >= 65:
        score += 15; signals.append(f"STRONG_RATE: ${job.hourly_max}/hr")
    elif job.fixed_amount and job.fixed_amount >= 1500:
        score += 20; signals.append(f"ELITE_FIXED: ${job.fixed_amount:,.0f}")
    elif job.fixed_amount and job.fixed_amount >= 700:
        score += 15; signals.append(f"STRONG_FIXED: ${job.fixed_amount:,.0f}")
    else:
        score += 15; signals.append("MEETS_MINIMUM_BUDGET")

    # ── 2. Domain exclusion (irrelevant categories with no GTM stack) ────────
    clay_match = bool(re.search(r'\bclay\b', full_text))
    has_any_stack = clay_match or bool(re.search(
        r'\bhubspot\b|\bsalesforce\b|\bmake\.com\b|\binstantly\b|\bapollo\b|'
        r'\battio\b|\blemlist\b|\bsmartlead\b|\bn8n\b|\bzoho\b|'
        r'\bgohighlevel\b|\bghl\b',
        full_text
    ))

    # Hard title filter — fires regardless of has_any_stack (skills ontology can't override title)
    title_irrelevant = re.search(
        r'\btypescript\b|\bcloudflare workers\b|\bsupabase\b|next\.?js|react native|'
        r'flutter|\bkubernetes\b|\bdocker\b|\bterraform\b|aws lambda|'
        r'\bphp\b|\bruby on rails\b|\bdjango\b|\blaravel\b',
        job.title.lower()
    )
    if title_irrelevant and not clay_match:
        return (0, [f"FILTERED: Irrelevant tech in title ({title_irrelevant.group()})"])

    # Salesforce dev/engineering roles — too technical, not GTM ops
    salesforce_dev_title = re.search(
        r'salesforce.*(integration engineer|developer|admin|apex|lwc|soql)|'
        r'salesforce integration',
        job.title.lower()
    )
    if salesforce_dev_title and not clay_match:
        return (0, [f"FILTERED: Salesforce dev role ({salesforce_dev_title.group()})"])

    # Course creation / instructor roles — not execution work
    if re.search(r'\binstructor\b|create.*course|build.*course|\bcourse creator\b', job.title.lower()):
        return (0, ["FILTERED: Course/instructor role"])

    # Generic operations manager without GTM qualifier — not relevant
    if re.search(r'\boperations manager\b', job.title.lower()):
        if not re.search(r'gtm|revenue|revops|sales.?ops|go.to.market|growth|marketing', job.title.lower()):
            return (0, ["FILTERED: Generic operations manager (no GTM qualifier)"])

    # Infrastructure / cloud engineering roles — not GTM
    if re.search(r'cloud.?infrastructure|cloud.?engineer|devops engineer|platform engineer|'
                 r'backend engineer|fullstack engineer|full.stack engineer|'
                 r'api.?integration engineer|data engineer|ml engineer|'
                 r'\bsre\b|site.?reliability', job.title.lower()):
        if not clay_match:
            return (0, ["FILTERED: Infrastructure/engineering role (not GTM)"])

    irrelevant_domain = re.search(
        r'3d model|3d architect|3d render|magento|shopify theme|wordpress theme|'
        r'woocommerce|packaging design|supplement|google tag manager|\bga4\b|'
        r'meta capi|meta pixel|confluence|ios app|android app|mobile app|'
        r'unreal engine|unity|game dev|'
        r'\btypescript\b|\bcloudflare workers\b|\bsupabase\b|next\.?js|react native|'
        r'flutter|\bkubernetes\b|\bdocker\b|\bterraform\b|aws lambda|'
        r'conversion tracking|server.side tracking|'
        r'google ads specialist|facebook ads|tiktok ads|'
        r'\bklaviyo\b|\brecharge\b|dtc brand|shopify store|'
        r'seo specialist|content writing|copywriting|'
        r'bookkeeping|accounting|tax prep|'
        r'google ads|google adwords|\bppc\b|pay.per.click|media buy|'
        r'performance marketing|programmatic|display advertising|'
        r'zendesk|freshdesk|intercom|customer support platform|'
        r'power ?bi|tableau|looker|data studio|'
        r'\bseo\b|search engine optim',
        full_text
    )
    if irrelevant_domain and not has_any_stack:
        return (0, ["FILTERED: Irrelevant domain (no GTM stack match)"])

    # ── 2b. GTM Relevance Gate ────────────────────────────────────────────────
    gtm_relevant = bool(re.search(
        r'gtm|go.to.market|outbound|inbound|lead gen|crm|revops|'
        r'revenue operations|sales.?ops|demand gen|account.based|abm|'
        r'prospecting|sequenc|cold email|enrichment|icp|'
        r'ideal customer|sales pipeline|sales automation|'
        r'marketing automation|campaign|outreach',
        full_text
    ))
    if not has_any_stack and not gtm_relevant and not clay_match:
        return (0, ["FILTERED: No GTM relevance (no stack + no GTM context)"])

    # ── 3. Stack Match (0-20 pts) ──────────────────────────────────────────────
    if clay_match:
        score += 15; signals.append("STACK: Clay")

    secondary_tools = {
        r'\bmake\.com\b|make com|\bintegromat\b': 'Make.com',
        r'\binstantly\b': 'Instantly',
        r'\bapollo\b': 'Apollo',
        r'\bhubspot\b': 'HubSpot',
        r'\bsalesforce\b': 'Salesforce',
        r'\battio\b': 'Attio',
        r'\blemlist\b': 'Lemlist',
        r'\bsmartlead\b': 'Smartlead',
        r'\bn8n\b': 'n8n',
        r'\bclaude\b|\banthropic\b': 'Claude/AI',
        r'\bzoho\b': 'Zoho',
        r'\bgohighlevel\b|\bghl\b': 'GHL',
    }

    matched_tools = []
    for pattern, name in secondary_tools.items():
        if re.search(pattern, full_text):
            matched_tools.append(name)

    if matched_tools:
        tool_score = min(len(matched_tools) * 3, 10)
        if not clay_match:
            tool_score = min(tool_score, 8)
        score += tool_score
        signals.append(f"TOOLS: {', '.join(matched_tools[:4])}")

    # ── 3. Architect Depth (0-20 pts) ─────────────────────────────────────────
    architect_patterns = {
        r'architect|infrastructure|system design|data model|schema': 'SYSTEMS_DESIGN',
        r'enrich|enrichment|data layer|signal layer': 'ENRICHMENT_ARCH',
        r'audit|overhaul|diagnos|assess|review.*setup': 'AUDIT_TAKEOVER',
        r'icp|ideal customer|persona|segmentat': 'ICP_RESEARCH',
        r'intent|trigger|signal.based|event.driven': 'SIGNAL_DETECTION',
        r'pipeline|funnel|workflow|engine': 'PIPELINE_BUILD',
        r'api.integrat|data.integrat|crm.integrat|bi.directional|sync|write.back|webhook': 'INTEGRATION_BUILD',
        r'strateg|consult|adviso|mentor|coach': 'STRATEGIC_ADVISORY',
    }

    arch_matches = []
    for pattern, label in architect_patterns.items():
        if re.search(pattern, full_text):
            arch_matches.append(label)

    if arch_matches:
        arch_score = min(len(arch_matches) * 5, 20)
        score += arch_score
        signals.append(f"DEPTH: {', '.join(arch_matches[:3])}")

    # ── 5. Anti-Signals (penalties) ───────────────────────────────────────────
    # Title-only check: VA/appointment-setter roles have these in the title, not body
    if re.search(r'cold call|telemarket|appointment.set|virtual.assist|data entry', job.title.lower()):
        score -= 30; signals.append("ANTI: VA/cold-call title")

    # Geographic restriction
    title_lower = job.title.lower()
    desc_lower = (job.description or "").lower()
    _geo_countries = (
        r'us only|usa only|united states only|us-based|usa-based|'
        r'based in (?:us|usa|united states|canada|australia|argentina|'
        r'latin america|latam|india|pakistan|brazil|mexico|philippines|'
        r'ukraine|nigeria|egypt)|'
        r'\(us\)|\(usa\)|\(us only\)|\(latam\)|\(latin america\)|\(argentina\)|'
        r'\(canada\)|\(australia\)|\(india\)|\(philippines\)'
    )

    _explicit_exclusion = re.compile(
        r'us only|usa only|united states only|us-based|usa-based|'
        r'north america only|'
        r'freelancers? from (?:the )?(?:us|usa|united states)|'
        r'(?:us|usa|north america) freelancers? only|'
        r'must be in (?:the )?(?:us|usa|united states|north america)|'
        r'(?:est|pst|cst|mst) (?:timezone|time zone|hours) required|'
        r'(?:us|usa) (?:citizenship|residents?) (?:only|required)|'
        r'based in (?:us|usa|united states|canada|australia|latin america|latam|india|philippines)|'
        r'\(us only\)|\(usa only\)|\(us\)|\(usa\)|\(latam\)|\(latin america\)'
    )

    if job.qualified_countries:
        # Structured Upwork qualifications field — only penalize explicit non-Poland restrictions
        poland_ok = any(
            c.lower() in ('poland', 'pl', 'europe', 'european union', 'eu', 'emea',
                          'worldwide', 'global', 'all countries', 'international')
            for c in job.qualified_countries
        )
        if not poland_ok:
            countries_str = ', '.join(job.qualified_countries[:3])
            score -= 25; signals.append(f"GEO: Explicitly restricted to {countries_str}")
    else:
        # Fall back to explicit restriction patterns in title and description only
        if re.search(_geo_countries, title_lower) or re.search(_explicit_exclusion, title_lower):
            score -= 20; signals.append("GEO: Location restricted (title) — excludes Poland")
        elif re.search(_explicit_exclusion, desc_lower):
            score -= 20; signals.append("GEO: Location restricted (description) — excludes Poland")

    if re.search(r'cold email|cold outreach', job.title.lower()):
        score -= 10; signals.append("ANTI: cold-email title")

    if job.min_jss_required and job.min_jss_required >= 90:
        score -= 15; signals.append(f"BARRIER: Requires {job.min_jss_required:.0f}% JSS")

    # GHL anti-signal only fires when Clay is absent (GHL+Clay is a valid combo)
    if re.search(r'gohighlevel|highlevel|\bghl\b', full_text) and not clay_match:
        score -= 10; signals.append("ANTI: GHL-only (not your stack)")

    # ── Freshness penalty ─────────────────────────────────────────────────────
    if job.posted_on:
        try:
            posted = datetime.fromisoformat(job.posted_on.replace('Z', '+00:00'))
            age_hours = (datetime.now(timezone.utc) - posted).total_seconds() / 3600
            if age_hours > 336:
                score -= 30; signals.append(f"STALE: Posted {age_hours/24:.0f}d ago — likely filled")
            elif age_hours > 120:
                score -= 20; signals.append(f"STALE: Posted {age_hours/24:.0f}d ago — high competition")
            elif age_hours > 72:
                score -= 10; signals.append(f"STALE: Posted {age_hours/24:.0f}d ago")
        except (ValueError, TypeError):
            pass

    # ── 5. Buyer Quality (0-15 pts, detail jobs only) ─────────────────────────
    if job.data_type == "detail":
        if job.payment_verified:
            score += 3; signals.append("BUYER: Verified payment")

        if job.client_total_spent and job.client_total_spent >= 10000:
            score += 5; signals.append(f"BUYER: ${job.client_total_spent:,.0f} spent")
        elif job.client_total_spent and job.client_total_spent >= 1000:
            score += 3; signals.append(f"BUYER: ${job.client_total_spent:,.0f} spent")

        if job.client_open_jobs is not None and job.client_open_jobs <= 1:
            if not job.client_total_spent or job.client_total_spent < 500:
                score += 4; signals.append("BUYER: First-time (high trust opportunity)")
            else:
                score += 4; signals.append("BUYER: Focused posting (single active job)")

        if job.total_applicants is not None:
            if job.total_applicants < 10:
                score += 5; signals.append(f"COMP: Low ({job.total_applicants} apps)")
            elif job.total_applicants < 20:
                score += 3; signals.append(f"COMP: Medium ({job.total_applicants} apps)")
            elif job.total_applicants >= 100:
                score -= 15; signals.append(f"COMP: Saturated ({job.total_applicants} apps)")
            elif job.total_applicants >= 40:
                score -= 5; signals.append(f"COMP: Crowded ({job.total_applicants} apps)")

    elif job.data_type == "private":
        # Compensate for missing buyer quality section on private listings
        score += 8; signals.append("PRIVATE_BASELINE: +8 (no buyer data available)")

    # ── 6. Expansion Potential (0-10 pts) ─────────────────────────────────────
    if re.search(r'phase|ongoing|long.term|retainer|recurring|extend|month.to.month', full_text):
        score += 5; signals.append("EXPAND: Ongoing/retainer signal")

    if re.search(r'document|sop|walkthrough|train|handoff|blueprint', full_text):
        score += 3; signals.append("EXPAND: Documentation premium")

    if re.search(r'founding|fractional|partner|co.build', full_text):
        score += 5; signals.append("EXPAND: Founding/partner role")

    # ── 7. AI/LLM Layer (0-10 pts) ────────────────────────────────────────────
    if re.search(r'\bai\b|claude|gpt|openai|llm|machine learning|agentic', full_text):
        gtm_context = any(
            re.search(p, full_text)
            for p in [r'enrich', r'outbound', r'pipeline', r'gtm', r'crm', r'lead']
        )
        if gtm_context:
            score += 10; signals.append("AI_GTM: AI + GTM intersection (rare combo)")
        else:
            score += 3; signals.append("AI: Mentioned but generic context")

    # ── 8. Description quality (+5 pts) ──────────────────────────────────────
    if len((job.description or "").split()) > 300:
        score += 5; signals.append("DESC_QUALITY: Detailed brief (300+ words)")

    # ── 9. Niche vertical (+5 pts) ────────────────────────────────────────────
    if re.search(
        r'healthcare|legal|fintech|real estate|recruitment|trucking|'
        r'insurance|solar|construction|hospitality|saas',
        full_text
    ):
        score += 5; signals.append("NICHE_VERTICAL: Industry-specific GTM")

    # ── 10. RevOps/CRM title multiplier (+8 pts) ─────────────────────────────
    if re.search(r'revops|revenue operations|crm architect|crm specialist|crm.+automation', job.title.lower()):
        if (job.hourly_max and job.hourly_max >= 50) or (job.fixed_amount and job.fixed_amount >= 500):
            score += 8; signals.append("REVOPS_PREMIUM: High-value category match")

    # ── 11. Private listing flag ───────────────────────────────────────────────
    if job.data_type == "private":
        signals.append("⚠️ PRIVATE: No client activity data — check manually")

    return (max(score, 0), signals)


def get_tier(score: int) -> str:
    from config import SCORE_APPLY_NOW, SCORE_STRONG_FIT
    if score >= SCORE_APPLY_NOW:
        return "APPLY_NOW"
    elif score >= SCORE_STRONG_FIT:
        return "STRONG_FIT"
    elif score >= 30:
        return "MAYBE"
    else:
        return "SKIP"


def tier_emoji(tier: str) -> str:
    return {
        "APPLY_NOW": "🔴",
        "STRONG_FIT": "🟡",
        "MAYBE": "⚪",
        "SKIP": "❌",
    }.get(tier, "")
