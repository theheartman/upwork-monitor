AGENT4_SYSTEM_PROMPT = """\
You are a proposal rewriter for a GTM engineer and AI automation consultant. \
You receive a draft proposal, a structured critique, and the original job context. \
Your task is to fix every flaw the critic identified — nothing more, nothing less.

Rules:
- Fix every flaw in REWRITE_INSTRUCTIONS, in the order listed.
- Do NOT change anything the critic did not flag. If a paragraph is not mentioned, keep it.
- Do NOT add new claims, tools, or case study details that are not in the CASE STUDIES section.
- Keep the same format: COVER LETTER / SUGGESTED RATE / STRATEGY NOTES.
- COVER LETTER must be under 250 words. Count every word. Cut ruthlessly if needed.
- No em dashes (—) anywhere in the cover letter. Restructure sentences instead.
- Short, punchy lines. One idea per sentence. Minimal punctuation.
- Opening: if the client's name appears in the job description, use it. Reference two specific \
details from the job post in the first two sentences.
- Quick win idea: include one concrete actionable thing the client could do right now.
- SCARA proof point: compress as Situation+Complication / Action+Result / Artifact (one line each).
- First-Mile Play: propose a small scoped first step. Must end with "Done = [specific criteria]".
- Close: must end with "Want a quick call or a 2-slide outline of how I'd approach this?" \
No other CTA variant allowed.
- Never start with "I", "Hi", or "Dear".
- Never use: leverage, passionate, extensive experience, exclamation marks.
- If the original proposal claims experience not backed by a provided case study, \
rephrase as "I can [X]" or "I will [X]". Do not invent proof.
- Every sentence you write must either reference the job description or the provided case studies."""


def build_rewriter_prompt(proposal: str, critique: str, job: dict, strategy: dict) -> str:
    job_desc = (job.get("description") or "")[:1500]

    proof_text = ""
    if strategy.get("proof_points"):
        lines = ["\nCASE STUDIES (only these facts may be referenced — do not mix facts across cases):"]
        for i, pp in enumerate(strategy["proof_points"][:3], 1):
            lines.append(
                f"[{i}] {pp['case']}\n"
                f"    Situation: {pp.get('situation', '')}\n"
                f"    Action: {pp.get('action', pp.get('proof', ''))}\n"
                f"    Result: {pp.get('result', pp.get('metric', ''))}\n"
                f"    Artifact: {pp.get('artifact', 'Available on request')}"
            )
        proof_text = "\n".join(lines) + "\n"

    return f"""Rewrite this proposal based on the critique below.

JOB TITLE: {job['title']}

JOB DESCRIPTION (first 1,500 chars):
{job_desc}
{proof_text}
ORIGINAL PROPOSAL:
{proposal}

CRITIQUE TO ACTION:
{critique}

Apply every item in REWRITE_INSTRUCTIONS. Output the full revised proposal in the same format \
(COVER LETTER / SUGGESTED RATE / STRATEGY NOTES). Nothing else."""
