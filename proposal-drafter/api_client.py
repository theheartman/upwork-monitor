import os
import re
from typing import Optional

import requests


MODEL = "claude-sonnet-4-6"


def generate_proposal(system_prompt: str, user_prompt: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 750,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        },
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def validate_proposal(text: str, proof_points: Optional[list] = None) -> list[str]:
    """Return list of quality warnings. Empty list = passed."""
    warnings = []

    first_word = text.split()[0].lower().rstrip(",'") if text.split() else ""
    if first_word in ("i", "hi", "dear", "hello"):
        warnings.append("WARN: Starts with greeting or 'I' — rewrite opening")

    word_count = len(text.split())
    if word_count > 250:
        warnings.append(f"WARN: Too long ({word_count} words) — cut to under 250")

    if word_count < 80:
        warnings.append(f"WARN: Too short ({word_count} words) — may seem low-effort")

    for phrase in ("passionate", "extensive experience", "leverage"):
        if phrase in text.lower():
            warnings.append(f"WARN: Contains '{phrase}' — replace")

    if text.count("!") > 1:
        warnings.append("WARN: Too many exclamation marks — remove")

    first_chunk = text[:150]
    if first_chunk.lstrip().startswith(("I ", "My ")):
        warnings.append("WARN: First sentence is about you, not their problem")

    # Fabrication detection — phrases that claim specific history without proof
    fabrication_patterns = [
        r"i'?ve done both",
        r"i'?ve built (both|this|similar|exactly)",
        r"i'?ve done (this|both|exactly|similar)",
        r"done (this|both) before",
        r"built (this|both) before",
        r"i'?ve (implemented|deployed|set up) (both|this|similar)",
        r"done it (both|before)",
    ]
    for pattern in fabrication_patterns:
        if re.search(pattern, text.lower()):
            warnings.append(
                f"FABRICATION RISK: '{re.search(pattern, text.lower()).group()}' — "
                "verify this is backed by a real case study or remove it"
            )

    # Check that claimed tools are grounded in proof points
    if proof_points:
        allowed_text = " ".join(
            f"{pp.get('proof', '')} {pp.get('case', '')}" for pp in proof_points
        ).lower()
        specific_claims = re.findall(
            r"(?:built|implemented|used|deployed|set up)\s+(?:a\s+)?([A-Za-z0-9\.\-]+(?: [A-Za-z0-9\.\-]+){0,3})",
            text.lower()
        )
        for claim in specific_claims:
            tool = claim.strip()
            if len(tool) > 4 and tool not in allowed_text:
                warnings.append(f"FABRICATION RISK: '{tool}' claimed but not in case studies — verify or remove")
                break  # one warning is enough

    return warnings
