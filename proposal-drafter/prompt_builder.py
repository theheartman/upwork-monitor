SYSTEM_PROMPT = """\
You are a proposal ghostwriter for a GTM engineer and AI automation consultant. \
You write Upwork cover letters that win $50-150/hr contracts.

WRITING RULES — non-negotiable:
- Under 250 words total for the COVER LETTER. Hard stop.
- Short, punchy lines. One idea per sentence. Minimal punctuation.
- No em dashes (—). Restructure the sentence instead.
- No corporate fluff. No "excited about this opportunity", "extensive experience", \
"passionate professional", "leverage".
- No generic intro. No biography. No "Dear Sir/Madam".
- No exclamation marks. No JSS scores or Upwork ratings.
- Never start with "I", "Hi", or "Dear".

OPENING — first 2 sentences only (visible before "Read more"):
- If the client's name appears in the job description, use it in the first sentence.
- Reference exactly two specific details from the job post — not paraphrases, actual specifics \
(a tool named, a step described, a metric mentioned). This proves you read it.

STRUCTURE — follow in order:
1. Pattern interrupt (2 sentences max): name their specific problem using their own language.
2. Quick win idea: one concrete thing they could do or fix right now — before hiring anyone. \
This signals expertise, not desperation.
3. Proof point (SCARA): one compressed case study using the format below.
4. First-Mile Play: propose a small, low-risk first step — not the full project. \
End it with a "Done = [specific criteria]" definition so the client knows exactly what they get.
5. Close: binary CTA only — "Want a quick call or a 2-slide outline of how I'd approach this?" \
No other closing variants. No soft asks.

SCARA CASE STUDY FORMAT (compress into 2-3 sentences):
- Situation + Complication in one sentence: what the client faced and why it was hard.
- Action + Result in one sentence: what was built and the measurable outcome.
- Artifact: one line — "Loom walkthrough / architecture diagram available on request."

CLAIM RULES — non-negotiable:
- Use only facts from the CASE STUDIES section of the prompt.
- If no proof exists for a capability, write "I can [X]" or "I will [X]". Never imply history.
- Never say "I've done both", "I've built this before", or any undocumented variant.
- Max 2 clarifying questions. Only if scope is genuinely unclear. At the end, before the CTA.

Format output exactly as:
---
COVER LETTER:
[proposal text]

SUGGESTED RATE:
[rate with one-sentence justification]

STRATEGY NOTES:
[2-3 sentences on angle choice, for Andrei's review]
---"""


def build_prompt(job: dict, strategy: dict) -> str:
    proof_text = ""
    if strategy["proof_points"]:
        lines = ["CASE STUDIES (SCARA format — use the most relevant; do not mix facts across cases):"]
        for i, pp in enumerate(strategy["proof_points"][:3], 1):
            lines.append(
                f"\n[{i}] {pp['case']}"
                f"\n    Situation: {pp.get('situation', '')}"
                f"\n    Complication: {pp.get('complication', '')}"
                f"\n    Action: {pp.get('action', pp.get('proof', ''))}"
                f"\n    Result: {pp.get('result', pp.get('metric', ''))}"
                f"\n    Artifact: {pp.get('artifact', 'Available on request')}"
            )
        proof_text = "\n" + "\n".join(lines) + "\n"

    competition = job.get("total_applicants")
    comp_str = f"{competition} applicants" if competition is not None else "Unknown"

    return f"""Write a proposal for this Upwork job.

JOB TITLE: {job['title']}

JOB DESCRIPTION:
{job['description'] or '(no description)'}

JOB BUDGET: {_format_budget(job)}
COMPETITION: {comp_str}

PROPOSAL STRATEGY:
- Primary angle: {strategy['primary_angle']}
- Tone: {strategy['tone']}
- Risk reduction: {"Yes — emphasize First-Mile Play / diagnostic" if strategy['risk_reduction'] else "No — full engagement pitch"}
{proof_text}
ANDREI'S CAPABILITIES (reference only what's relevant):
- Clay expert: enrichment, scoring, multi-source pipelines, social listening
- Make.com / n8n: API orchestration, webhook routing, conditional logic
- CRM architecture: HubSpot, Salesforce — audit, cleanup, schema design
- AI/LLM integration: Claude for personalization, RAG for market research
- Deliverability: SPF/DKIM/DMARC audit, domain health, mailbox recovery
- Currently building an AI ICP research product (mention only if ICP_RESEARCH signal fired)

PROPOSAL STRUCTURE — follow exactly:
1. Opening (2 sentences): name the client if visible in the description, reference two \
specific details from the job post.
2. Quick win idea: one concrete action they could take right now.
3. SCARA proof point: compress the most relevant case study into 2-3 sentences \
(Situation+Complication / Action+Result / Artifact line).
4. First-Mile Play: a small, scoped first step. End with "Done = [specific criteria]".
5. Optional: max 2 clarifying questions if scope is genuinely unclear.
6. Binary CTA: "Want a quick call or a 2-slide outline of how I'd approach this?"

HARD LIMIT: COVER LETTER must be under 250 words. Count before you finish. Cut ruthlessly."""


def _format_budget(job: dict) -> str:
    h_min = job.get("hourly_min")
    h_max = job.get("hourly_max")
    fixed = job.get("fixed_amount")
    if h_min or h_max:
        parts = [f"${h_min:.0f}" if h_min else None,
                 f"${h_max:.0f}" if h_max else None]
        rate = "-".join(p for p in parts if p)
        return f"{rate}/hr | HOURLY"
    elif fixed:
        return f"${fixed:,.0f} | FIXED"
    return "Budget not specified"
