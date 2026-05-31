import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from case_studies import get_proof_points

SIGNAL_TO_ANGLE = {
    "ENRICHMENT_ARCH":    "enrichment_architect",
    "SYSTEMS_DESIGN":     "systems_architect",
    "AUDIT_TAKEOVER":     "audit_rescue",
    "ICP_RESEARCH":       "icp_strategist",
    "SIGNAL_DETECTION":   "intent_engineer",
    "PIPELINE_BUILD":     "pipeline_builder",
    "INTEGRATION_BUILD":  "integration_specialist",
    "STRATEGIC_ADVISORY": "strategic_advisor",
}

PRIORITY = [
    "SIGNAL_DETECTION",
    "ICP_RESEARCH",
    "ENRICHMENT_ARCH",
    "AUDIT_TAKEOVER",
    "SYSTEMS_DESIGN",
    "STRATEGIC_ADVISORY",
    "PIPELINE_BUILD",
    "INTEGRATION_BUILD",
]


def select_strategy(signals: list[str]) -> dict:
    """Given scorer signals, return proposal strategy dict."""
    depth_signals = _extract_depth_signals(signals)

    primary = "pipeline_builder"
    for p in PRIORITY:
        if p in depth_signals:
            primary = SIGNAL_TO_ANGLE[p]
            break

    tone = "consultative"
    if any("FOUNDING" in s or "PARTNER" in s.upper() for s in signals):
        tone = "partner"
    elif any("STACK: Clay" in s for s in signals) and len(depth_signals) >= 3:
        tone = "technical"

    risk_reduction = any(
        "First-time" in s or "AUDIT" in s.upper()
        for s in signals
    )

    return {
        "primary_angle": primary,
        "proof_points": get_proof_points(signals),
        "tone": tone,
        "risk_reduction": risk_reduction,
        "depth_signals": depth_signals,
    }


def _extract_depth_signals(signals: list[str]) -> list[str]:
    """Pull individual signal keys out of formatted signal strings."""
    keys = []
    for s in signals:
        if "DEPTH:" in s:
            parts = s.replace("DEPTH:", "").strip().split(",")
            keys.extend(p.strip() for p in parts)
        for key in SIGNAL_TO_ANGLE:
            if key in s and key not in keys:
                keys.append(key)
    return keys
