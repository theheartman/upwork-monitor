# Agent 2: Proposal Drafter — Architecture Spec

## Executive Summary

A CLI tool that takes a scored Upwork job from Agent 1's database, matches it against your case studies and signal-to-angle mapping, and generates a tailored proposal draft using Claude Sonnet. The output is a ready-to-paste cover letter structured around what actually wins at the $50+/hr tier.

---

## 1. System Overview

```
┌─────────────────┐     ┌───────────────┐     ┌──────────────┐     ┌──────────┐
│ Agent 1 SQLite   │────▶│ Signal Router │────▶│ Prompt       │────▶│ Claude   │
│ (scored job)     │     │ + Case Study  │     │ Assembler    │     │ Sonnet   │
│                  │     │ Matcher       │     │              │     │ API      │
└─────────────────┘     └───────────────┘     └──────────────┘     └──────────┘
                                                                        │
                                                                        ▼
                                                                   ┌──────────┐
                                                                   │ Proposal │
                                                                   │ Output   │
                                                                   │ (stdout  │
                                                                   │  + clip) │
                                                                   └──────────┘
```

**Flow:**
1. User provides a job_id (from Agent 1's Telegram alert or DB)
2. Signal router reads the job's scored signals and selects the proposal strategy
3. Case study matcher picks the 1–2 most relevant proof points
4. Prompt assembler builds a structured prompt with all context
5. Claude Sonnet generates the proposal draft
6. Output is printed to stdout and optionally copied to clipboard

---

## 2. The Proposal Framework

### 2.1 Why This Structure Works

Your 3 hires and 5 viewed applications share a pattern: the client saw something in the first two sentences that signaled "this person already understands my problem." None of your wins came from generic introductions. The framework below is reverse-engineered from what actually converted.

### 2.2 Proposal Structure (4 sections, ~2,000 chars total)

#### Section 1: The Pattern Interrupt (first 2 sentences, <150 chars)

This is the only part visible in the Upwork feed before "Read more." It must demonstrate immediate understanding of their specific problem — not your qualifications.

**Rules:**
- Reference something specific FROM their job description
- Name a concrete problem or observation, not a capability
- Never start with "I" or "Hi, I'm..."
- Never start with "I'd love to help" or "I'm excited about this opportunity"

**Examples by signal:**

| Signal | Pattern Interrupt |
|---|---|
| AUDIT_TAKEOVER | "Your [tool] setup has [specific pattern from description] — that's usually a sign of [specific technical issue]. I've fixed this exact problem for a [industry] company." |
| ENRICHMENT_ARCH | "Enriching [X] records across [sources they mentioned] without burning credits on dead data is the hard part. I built a system that solved this at 30K-contact scale." |
| ICP_RESEARCH | "The gap between 'we know our ICP' and 'our data actually reflects our ICP' is where most outbound breaks. I've closed that gap using AI research across 58 industry reports." |
| SIGNAL_DETECTION | "Waiting for press releases to trigger outreach means you're always late. I built an intent engine that catches signals like [relevant trigger] before they hit the news." |
| SYSTEMS_DESIGN | "A [tool A] + [tool B] stack only works when the data model underneath is right. Most setups I inherit have the integrations but not the schema — that's where breakage starts." |

#### Section 2: The Proof Point (1 paragraph, ~400 chars)

One specific result from the most relevant case study. Not a portfolio link — a number.

**Rules:**
- Lead with the metric, not the client name
- Use anonymized industry descriptors ("a workforce management SaaS," "a data center CMMS provider")
- Connect the proof to their specific situation
- One proof point only — more dilutes the signal

**Mapping:** Use `case_studies.get_proof_points(signals)[0]` — the highest-priority match.

#### Section 3: The Scope Sketch (3–5 bullets, ~600 chars)

A lightweight Phase 1 proposal that shows you already know what needs to happen. Not a full SOW — a "here's what the first engagement looks like."

**Rules:**
- Frame as "Phase 1" or "Diagnostic" or "Foundation Sprint"
- 3–5 concrete deliverables, not vague promises
- Include one deliverable that's a handoff artifact (documentation, SOP, schema diagram)
- If the job signals EXPAND/ongoing, mention the Phase 2 path
- If the job signals BUYER: First-time, emphasize low commitment ("1-week diagnostic")

**Example:**
```
Phase 1 — Foundation Sprint (1–2 weeks):
• Audit your current [tool] setup and document the data flow gaps
• Build the enrichment pipeline: [source] → Clay → [destination CRM]
• Implement deduplication + credit-burn prevention logic
• Deliver a documented architecture diagram + SOP for your team

This gives you a working system and a clear picture of what Phase 2
(ongoing enrichment + campaign integration) would look like.
```

#### Section 4: The Close (1–2 sentences, <150 chars)

**Rules:**
- No begging, no "looking forward to hearing from you"
- Suggest a specific next step
- If low competition (<10 apps): be conversational ("Happy to walk through this on a quick call")
- If high competition (>30 apps): create urgency via specificity ("I can start this week — I have a similar pipeline architecture running for another client that maps closely")

---

## 3. Signal Router

The signal router determines which proposal strategy to use based on the scorer's output. It selects the primary angle, the case study, and the tone.

### 3.1 Strategy Selection

```python
# strategy_router.py

from case_studies import get_proof_points

SIGNAL_TO_ANGLE = {
    "ENRICHMENT_ARCH":     "enrichment_architect",
    "SYSTEMS_DESIGN":      "systems_architect",
    "AUDIT_TAKEOVER":      "audit_rescue",
    "ICP_RESEARCH":        "icp_strategist",
    "SIGNAL_DETECTION":    "intent_engineer",
    "PIPELINE_BUILD":      "pipeline_builder",
    "INTEGRATION_BUILD":   "integration_specialist",
    "STRATEGIC_ADVISORY":  "strategic_advisor",
}

def select_strategy(signals: list[str]) -> dict:
    """
    Given a list of scorer signals, return the proposal strategy.
    
    Returns:
        {
            "primary_angle": str,     # which archetype to lead with
            "proof_points": list,     # matched case study proof points
            "tone": str,              # "consultative" | "technical" | "partner"
            "risk_reduction": bool,   # whether to emphasize Phase 1 / diagnostic
            "mirror_language": list,  # specific terms from the job to echo back
        }
    """
    # Extract depth signals
    depth_signals = []
    for s in signals:
        if "DEPTH:" in s:
            parts = s.replace("DEPTH:", "").strip().split(",")
            depth_signals.extend([p.strip() for p in parts])
    
    # Determine primary angle (first match in priority order)
    priority = [
        "SIGNAL_DETECTION",   # rarest, highest differentiation
        "ICP_RESEARCH",       # maps to your AI product
        "ENRICHMENT_ARCH",    # core Clay competency
        "AUDIT_TAKEOVER",     # proven win pattern
        "SYSTEMS_DESIGN",     # architect positioning
        "STRATEGIC_ADVISORY", # consultant positioning
        "PIPELINE_BUILD",     # builder positioning
        "INTEGRATION_BUILD",  # integration work
    ]
    
    primary = "pipeline_builder"  # default
    for p in priority:
        if p in depth_signals:
            primary = SIGNAL_TO_ANGLE[p]
            break
    
    # Get proof points
    proof_points = get_proof_points(signals)
    
    # Determine tone
    tone = "consultative"  # default
    if any("FOUNDING" in s or "PARTNER" in s.upper() for s in signals):
        tone = "partner"
    elif any("STACK: Clay" in s for s in signals) and len(depth_signals) >= 3:
        tone = "technical"
    
    # Risk reduction flag
    risk_reduction = any(
        "First-time" in s or "AUDIT" in s.upper()
        for s in signals
    )
    
    return {
        "primary_angle": primary,
        "proof_points": proof_points,
        "tone": tone,
        "risk_reduction": risk_reduction,
    }
```

---

## 4. Prompt Assembly

### 4.1 System Prompt (constant)

```
You are a proposal ghostwriter for a GTM engineer and AI automation
consultant. You write Upwork cover letters that win $50-150/hr contracts.

Your writing style:
- Direct. No filler, no pleasantries, no "I'm excited about this opportunity."
- Technical but not jargon-heavy. You sound like an architect, not a vendor.
- Specific. Every sentence references something from the job description
  or a concrete result from past work.
- Short. Total proposal: 1,500-2,000 characters. Not a word more.

Your proposals NEVER:
- Start with "I" or "Hi, I'm" or "Dear"
- Include phrases like "passionate professional" or "extensive experience"
- List generic skills without connecting them to the client's problem
- Use exclamation marks
- Mention JSS scores or Upwork ratings
- Use the word "leverage"

The first 2 sentences (~150 chars) must be a "pattern interrupt" — a 
specific observation about the client's problem that proves you already
understand their situation. This is the only part visible before 
"Read more" on Upwork.

Format the output as:
---
COVER LETTER:
[the proposal text]

SUGGESTED RATE:
[hourly rate or fixed price with brief justification]

STRATEGY NOTES:
[2-3 sentences explaining why you chose this angle, for Andrei's review]
---
```

### 4.2 User Prompt (assembled per job)

```python
def build_prompt(job: dict, strategy: dict) -> str:
    """Assemble the user prompt from job data and strategy."""
    
    proof_text = ""
    if strategy["proof_points"]:
        pp = strategy["proof_points"][0]
        proof_text = f"""
MOST RELEVANT CASE STUDY:
- Client type: {pp['case']}
- What was done: {pp['proof']}
- Key metric: {pp['metric']}
"""

    return f"""
Write a proposal for this Upwork job.

JOB TITLE: {job['title']}

JOB DESCRIPTION:
{job['description']}

JOB BUDGET: {_format_budget(job)}
COMPETITION: {job.get('total_applicants', 'Unknown')} applicants

PROPOSAL STRATEGY:
- Primary angle: {strategy['primary_angle']}
- Tone: {strategy['tone']}
- Risk reduction: {"Yes — emphasize Phase 1 / diagnostic" if strategy['risk_reduction'] else "No — full engagement pitch"}

{proof_text}

ANDREI'S CAPABILITIES (reference only what's relevant):
- Clay expert: enrichment, scoring, multi-source pipelines
- Make.com / n8n: API orchestration, webhook routing, conditional logic
- CRM architecture: HubSpot, Salesforce — audit, cleanup, schema design
- AI/LLM integration: Claude for personalization, RAG for market research
- Deliverability: SPF/DKIM/DMARC audit, domain health, mailbox recovery
- Currently building an AI ICP research product (mention only if ICP_RESEARCH signal fired)

PROPOSAL STRUCTURE:
1. Pattern interrupt (first 2 sentences, <150 chars total — this is visible in the feed)
2. Proof point (1 paragraph referencing the case study above)
3. Scope sketch (Phase 1 with 3-5 bullet deliverables)
4. Close (1-2 sentences with specific next step)

Total length: 1,500-2,000 characters. No more.
"""
```

---

## 5. Claude API Integration

### 5.1 API Call

```python
import requests

def generate_proposal(system_prompt: str, user_prompt: str) -> str:
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": os.getenv("ANTHROPIC_API_KEY"),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1500,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "system": system_prompt,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["content"][0]["text"]
```

### 5.2 Rate Limiting

Sonnet is cheap (~$3/M input, $15/M output tokens). Each proposal uses ~2K input + ~500 output tokens. At 10 proposals/day, that's ~$0.10/day. No rate limiting needed for this volume.

---

## 6. CLI Interface

```bash
# Generate proposal for a specific job from the database
python draft.py <job_id>

# Generate proposal for the highest-scored unprocessed job
python draft.py --top

# Generate proposals for all APPLY_NOW jobs from today
python draft.py --tier APPLY_NOW

# Dry run: show strategy selection without calling API
python draft.py <job_id> --dry-run
```

### 6.1 Output

```
═══════════════════════════════════════════════════════════
 🔴 APPLY NOW — Score: 77
 Expert GTM Data Engineer — Make.com, Clay, AirTable & Winmo API
 $2,000 fixed | 8 applicants
═══════════════════════════════════════════════════════════

COVER LETTER:
Building a source-agnostic enrichment engine across Winmo, AirTable,
and HubSpot means getting the dedup logic right before you burn a
single enrichment credit. I've built this exact pipeline for an
enterprise tech sales org — 4 data sources into one scoring engine
using Clay + Make.com.

That project consolidated Demandbase, Albacross, ActiveCampaign, and
internal CRM data into a unified pipeline. The scoring matrix (0-100)
weighted headcount, industry fit, and engagement signals. We validated
the top 50 ranked outputs with the sales team before scaling — no
wasted credits, no garbage data.

Phase 1 — Foundation Build (1-2 weeks):
• Map the Winmo API → Clay enrichment flow with dedup at ingestion
• Build the AirTable staging layer for QA before HubSpot push
• Implement the relational write-back loop into HubSpot
• Deliver architecture diagram + data dictionary for your team

I can start this week. Happy to walk through the pipeline architecture
on a 15-minute call.

SUGGESTED RATE:
$2,000 fixed — matches the posted budget and aligns with the
scope of a 1-2 week foundation build.

STRATEGY NOTES:
Led with enrichment architecture angle because ENRICHMENT_ARCH +
SYSTEMS_DESIGN were the primary depth signals. Used the Enterprise
Scoring Engine case study (4 data sources → unified pipeline) because
it directly mirrors the multi-source API integration described in the
job. Proposed Phase 1 scope to reduce risk for the buyer.

═══════════════════════════════════════════════════════════
 📋 Copied to clipboard
═══════════════════════════════════════════════════════════
```

---

## 7. File Structure

```
proposal-drafter/
├── draft.py              # CLI entry point
├── strategy_router.py    # Signal → strategy mapping
├── prompt_builder.py     # Assemble system + user prompts
├── api_client.py         # Claude Sonnet API call
├── case_studies.py        # Copied from Agent 1 (or symlinked)
├── .env                  # ANTHROPIC_API_KEY
└── requirements.txt      # requests, python-dotenv
```

Agent 2 reads from Agent 1's SQLite database directly. No data duplication. The `DB_PATH` is imported from Agent 1's `config.py` or set via env var.

---

## 8. Configuration

### .env

```bash
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx

# Path to Agent 1's database (defaults to ../upwork-monitor/db/jobs.db)
AGENT1_DB_PATH=../upwork-monitor/db/jobs.db
```

### Dependencies

```
requirements.txt:
requests>=2.31.0
python-dotenv>=1.0.0
```

---

## 9. Quality Guardrails

### 9.1 Pre-send Checklist (automated)

Before displaying the proposal, run these checks:

```python
def validate_proposal(text: str) -> list[str]:
    """Return list of warnings. Empty = passed."""
    warnings = []
    
    if text.lower().startswith(("i ", "i'", "hi", "dear", "hello")):
        warnings.append("WARN: Starts with 'I' or greeting — rewrite opening")
    
    if len(text) > 2500:
        warnings.append(f"WARN: Too long ({len(text)} chars) — trim to <2,000")
    
    if len(text) < 800:
        warnings.append(f"WARN: Too short ({len(text)} chars) — may seem low-effort")
    
    if "passionate" in text.lower() or "extensive experience" in text.lower():
        warnings.append("WARN: Contains filler phrases — remove")
    
    if "leverage" in text.lower():
        warnings.append("WARN: Contains 'leverage' — replace with specific verb")
    
    if text.count("!") > 1:
        warnings.append("WARN: Too many exclamation marks — remove")
    
    # Check first 150 chars for pattern interrupt quality
    first_chunk = text[:150]
    if "I " in first_chunk[:5] or "My " in first_chunk[:5]:
        warnings.append("WARN: First sentence is about you, not their problem")
    
    return warnings
```

### 9.2 Feedback Loop

After submitting a proposal, manually update the job in Agent 1's database:

```bash
# Mark as applied
python draft.py <job_id> --mark-applied

# Record outcome (after client responds)
python draft.py <job_id> --outcome viewed
python draft.py <job_id> --outcome interviewed
python draft.py <job_id> --outcome hired
python draft.py <job_id> --outcome rejected
```

This feeds back into the scoring model validation from Agent 1's spec — after 2 weeks, correlate proposal angles with outcomes to see which strategies actually convert.

---

## 10. What This Does NOT Do (by design)

- **Does not auto-submit proposals.** The output is a draft for your review. You paste it into Upwork manually. This is intentional — you need to read the description yourself and verify the angle makes sense.

- **Does not answer client screening questions.** If the job has custom questions, you answer those yourself. The proposal draft covers the cover letter only.

- **Does not set the bid amount.** It suggests a rate with justification, but you decide the final number based on your pipeline and the specific client.

- **Does not handle follow-up messages.** First-touch proposals only. Conversation management is a different problem.
