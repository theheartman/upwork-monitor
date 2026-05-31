# case_studies.py — maps scorer signals to proof points for proposal generation
#
# Each entry follows SCARA format:
#   situation   — context/client background
#   complication — the specific problem that needed solving
#   action      — what was built/done
#   result      — measurable outcome
#   artifact    — proof available (Loom, diagram, doc)
#   metric      — single headline number for quick reference

SIGNAL_TO_PROOF = {
    "ENRICHMENT_ARCH": {
        "case": "Data Center CMMS Provider",
        "situation": "B2B software company with 30K+ Salesforce contacts accumulated over years, unknown data quality",
        "complication": "Sales team wasting time on bounced emails and wrong decision-makers; CRM was a liability, not an asset",
        "action": "Enriched all 30,215 contacts, validated 24,949 (82%), mapped 7,300 job-changers to current roles using multi-source Clay waterfall",
        "result": "82% validation rate; clean, routable CRM ready for outreach with no manual scrubbing",
        "artifact": "Before/after data quality report available",
        "metric": "82% validation rate across 30K contacts",
        "proof": "Enriched 30,215 Salesforce contacts, validated 24,949 (82% rate), mapped 7,300 job-changers to new roles",
    },
    "ICP_RESEARCH": {
        "case": "Workforce Management SaaS",
        "situation": "SaaS company entering a complex multi-stakeholder market with no validated ICP definition",
        "complication": "Messaging was generic across all segments; couldn't identify which buyer persona or vertical to prioritize for outbound",
        "action": "Built custom RAG knowledge base synthesizing 58 industry reports into campaign angles and precise ICP definitions per vertical",
        "result": "3 defined ICPs with distinct messaging angles — outreach pivoted from broad to targeted within one sprint",
        "artifact": "Loom walkthrough of the RAG pipeline available on request",
        "metric": "58 industry reports synthesized into actionable ICP targeting",
        "proof": "Developed custom RAG knowledge base from 58 industry reports to synthesize campaign angles and map precise ICPs for complex multi-stakeholder markets",
    },
    "SIGNAL_DETECTION": {
        "case": "Data Center CMMS Provider",
        "situation": "CMMS software company targeting new data center builds, but press releases came too late — competitors were already in the deal",
        "complication": "No public signal existed for early-stage construction; by the time a facility was announced, 3 other vendors had already made contact",
        "action": "Built first-mover intent engine in Clay capturing land acquisition records, utility permit applications, and construction filings before public announcements",
        "result": "First-mover advantage on net-new facility builds; sales team reaching decision-makers before RFP stage",
        "artifact": "Loom walkthrough of the intent detection workflow available on request",
        "metric": "First-mover advantage on net-new builds before press release",
        "proof": "Built a first-mover intent engine capturing land acquisitions, utility requests, and permit applications — identifying net-new facility builds before press releases",
    },
    "AUDIT_TAKEOVER": {
        "case": "Workforce Management SaaS",
        "situation": "Outbound program with 10,000 leads in pipeline and declining reply rates over 3 months",
        "complication": "Unknown whether the problem was list quality, messaging, timing, or ICP — no data to diagnose",
        "action": "Audited all 10K leads and 238 human responses; diagnosed messaging failure as primary cause — hooks were high-friction, not consultative",
        "result": "Messaging strategy rebuilt from response data; outreach pivoted to consultative angle with measurable improvement in positive reply rate",
        "artifact": "Audit framework and response analysis doc available on request",
        "metric": "10K leads audited, messaging strategy rebuilt from response data",
        "proof": "Audited 10,000 leads and 238 human responses to diagnose messaging performance, pivoting from high-friction hooks to consultative outreach",
    },
    "PIPELINE_BUILD": {
        "case": "Data Center CMMS Provider",
        "situation": "ABM campaign needed to run across hundreds of target accounts with personalized outreach at each step",
        "complication": "Manual process capped at ~50 accounts before quality degraded; scaling required removing humans from the loop without removing personalization",
        "action": "Architected always-on ABM engine: Clay tables feeding 20-point enrichment into Claude personalization layer, output to sequencing platform — fully automated",
        "result": "Fully automated ABM pipeline with 20-point personalization per account; campaign runs without manual intervention",
        "artifact": "Loom walkthrough of the Clay table architecture available on request",
        "metric": "Fully automated ABM pipeline with 20-point personalization",
        "proof": "Architected always-on ABM engine: Clay tables → Claude personalization (20 data points) → sequencing platform, fully automated",
    },
    "STRATEGIC_ADVISORY": {
        "case": "Workforce Management SaaS",
        "situation": "GTM engine built on unvalidated infrastructure, broad ICP, and messaging that hadn't been tested against real responses",
        "complication": "Poor deliverability (SPF/DKIM/DMARC gaps) and unfocused positioning were compounding — hard to diagnose root cause",
        "action": "Led full audit: infrastructure hardening, messaging pivot from 238 response analysis, ICP redefinition across 3 verticals",
        "result": "Complete GTM engine rebuilt from infrastructure to messaging — delivered as documented SOPs the team could run independently",
        "artifact": "Audit framework and SOP documentation available on request",
        "metric": "Full GTM engine from infrastructure to messaging",
        "proof": "Led end-to-end GTM strategy including infrastructure audit (SPF/DKIM/DMARC), messaging pivot based on response analysis, and ICP redefinition across 3 verticals",
    },
}


def get_proof_points(signals: list[str]) -> list[dict]:
    """Given a list of scorer signal strings, return matching proof points
    ordered by relevance (most specific first)."""
    signal_keys = set()
    for s in signals:
        if "DEPTH:" in s:
            parts = s.replace("DEPTH:", "").strip().split(",")
            for p in parts:
                signal_keys.add(p.strip())
        for key in SIGNAL_TO_PROOF:
            if key in s:
                signal_keys.add(key)

    seen_cases = set()
    results = []

    priority = [
        "SIGNAL_DETECTION", "ICP_RESEARCH", "ENRICHMENT_ARCH",
        "AUDIT_TAKEOVER", "PIPELINE_BUILD", "STRATEGIC_ADVISORY",
    ]

    for key in priority:
        if key in signal_keys and key in SIGNAL_TO_PROOF:
            proof = SIGNAL_TO_PROOF[key]
            if proof["case"] not in seen_cases:
                seen_cases.add(proof["case"])
                results.append(proof)

    return results
