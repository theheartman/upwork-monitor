# Proposal Pipeline — Agent Definitions

Three agents run in sequence to produce a final Upwork proposal.

```
Job from DB
    │
    ▼
[Agent 2] Draft        ← prompt_builder.py
    │
    ▼
[Agent 3] Critique     ← critic.py
    │
    ├── PASS    → use draft as-is
    ├── REJECT  → abort, review manually
    └── NEEDS_REVISION
            │
            ▼
        [Agent 4] Rewrite   ← rewriter.py
            │
            ▼
        Validator           ← validator.py
            │
            ▼
        Final proposal → stdout + clipboard
```

## Files

| Agent | Definition | Code |
|-------|-----------|------|
| Agent 2 — Drafter | [agent2_drafter.md](agent2_drafter.md) | `prompt_builder.py` |
| Agent 3 — Critic | [agent3_critic.md](agent3_critic.md) | `critic.py` |
| Agent 4 — Rewriter | [agent4_rewriter.md](agent4_rewriter.md) | `rewriter.py` |

## Shared context passed to all agents

- **Job data**: title, description (first 1,500 chars), budget, competition
- **Strategy**: primary angle, tone, risk reduction flag
- **Case studies**: up to 3 matching SCARA proof points from `case_studies.py`

## Hard limits enforced across all agents

- Cover letter: under 250 words
- No em dashes (—) anywhere in the cover letter
- No banned words: `leverage`, `passionate`, `extensive experience`
- No exclamation marks
- Never start with "I", "Hi", or "Dear"
- All claims must be backed by a provided case study — otherwise phrase as "I can [X]" or "I will [X]"
