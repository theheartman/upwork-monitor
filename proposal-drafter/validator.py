"""Post-rewrite automated checks — runs after Agent 4 output."""
import re
from typing import Optional


BANNED_WORDS = ["leverage", "passionate", "extensive experience", "synergy", "game-changer"]


def validate_final(text: str, proof_points: Optional[list] = None) -> list[str]:
    """Returns list of blocking issues. Empty = cleared for clipboard."""
    issues = []

    cover = _extract_cover_letter(text)
    word_count = len(cover.split())

    # Length
    if word_count > 250:
        issues.append(f"TOO_LONG: Cover letter is {word_count} words (limit 250)")

    if word_count < 80:
        issues.append(f"TOO_SHORT: Cover letter is {word_count} words (minimum 80)")

    # Opener
    first_word = cover.split()[0].lower().rstrip(",'") if cover.split() else ""
    if first_word in ("i", "hi", "dear", "hello"):
        issues.append("BAD_OPENER: Starts with greeting or 'I'")

    # Banned words
    for word in BANNED_WORDS:
        if word in cover.lower():
            issues.append(f"BANNED_WORD: '{word}' — remove it")

    # Em dash check
    if "—" in cover:
        count = cover.count("—")
        issues.append(f"EM_DASH: {count} em dash(es) found — rewrite those sentences")

    # Exclamation marks
    if cover.count("!") > 1:
        issues.append(f"EXCLAMATION: {cover.count('!')} found — max 1 allowed")

    # Vague client references — must not call client "you guys" or "your team" without specifics
    if re.search(r'\byou guys\b', cover.lower()):
        issues.append("VAGUE_CLIENT: 'you guys' — too casual, replace with specific reference")

    # Tool mirroring — tools mentioned in the proposal must appear in any proof point
    if proof_points:
        allowed_text = " ".join(
            f"{pp.get('proof', '')} {pp.get('case', '')}" for pp in proof_points[:3]
        ).lower()
        tool_claims = re.findall(
            r"(?:built|implemented|used|deployed|set up|ran|created)\s+"
            r"(?:a\s+|an\s+)?([A-Za-z0-9\.\-]+(?: [A-Za-z0-9\.\-]+){0,3})",
            cover.lower()
        )
        for tool in tool_claims:
            tool = tool.strip()
            if len(tool) > 4 and tool not in allowed_text:
                issues.append(
                    f"UNGROUNDED_CLAIM: '{tool}' not found in case study — verify or remove"
                )
                break

    # Structure check — must have all three sections
    for section in ("COVER LETTER:", "SUGGESTED RATE:", "STRATEGY NOTES:"):
        if section not in text:
            issues.append(f"MISSING_SECTION: '{section}' not found in output")

    return issues


def _extract_cover_letter(text: str) -> str:
    lines = text.splitlines()
    in_letter = False
    letter_lines = []
    for line in lines:
        if line.strip() == "COVER LETTER:":
            in_letter = True
            continue
        if in_letter and line.strip().startswith("SUGGESTED RATE:"):
            break
        if in_letter:
            letter_lines.append(line)
    return "\n".join(letter_lines).strip() if letter_lines else text
