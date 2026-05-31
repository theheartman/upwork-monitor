# Skill: Draft Proposal

**What it does:** Берёт вакансию из SQLite по `job_id` и прогоняет через пайплайн Agent 2 → Agent 3 → Agent 4: draft → critique → rewrite. Финальный cover letter копируется в буфер обмена.

**Trigger:** вызывается напрямую через `skills/draft_proposal.py` или из `proposal-drafter/draft.py`.

---

## Вызов

```bash
# Полный пайплайн для конкретной вакансии
python skills/draft_proposal.py <job_id>

# Топ-1 по score среди не поданных
python skills/draft_proposal.py --top

# Все вакансии тира APPLY_NOW за сегодня (с паузой между)
python skills/draft_proposal.py --tier APPLY_NOW
python skills/draft_proposal.py --tier STRONG_FIT

# Показать стратегию без API-вызова
python skills/draft_proposal.py <job_id> --dry-run

# Только Agent 2 (draft), без critique и rewrite
python skills/draft_proposal.py <job_id> --raw

# Agent 2 + 3 (critique), без rewrite
python skills/draft_proposal.py <job_id> --critique-only

# Отметить как поданную
python skills/draft_proposal.py <job_id> --mark-applied

# Записать исход
python skills/draft_proposal.py <job_id> --outcome hired
python skills/draft_proposal.py <job_id> --outcome rejected
```

---

## Flow

```
job_id / --top / --tier
    │
    ▼
load_job() из SQLite (jobs.db)
    │
    ▼
strategy_router.select_strategy(signals)   # сигналы → угол атаки, тон, case study
    │
    ▼
Agent 2: prompt_builder → Claude Sonnet    # draft cover letter
    │
    ▼
Agent 3: critic → VERDICT                  # PASS / NEEDS_REVISION / REJECT
    │
    ├── PASS      → используем draft
    ├── REJECT    → прерываем пайплайн
    └── NEEDS_REVISION
            │
            ▼
        Agent 4: rewriter → Claude Sonnet  # финальный rewrite
            │
            ▼
        validator.validate_final()         # word count, em dashes, запрещённые фразы
            │
            ▼
        stdout + pbcopy (буфер обмена)
```

---

## Входные данные

| Параметр | Источник | Описание |
|---|---|---|
| `job_id` | аргумент CLI | URL вакансии (PK в jobs.db) |
| `--top` | флаг | Берёт строку с MAX(score) WHERE applied=0 |
| `--tier` | флаг | Все вакансии тира за сегодня, applied=0 |
| Сигналы, описание, бюджет | SQLite `jobs` | Передаются в prompt_builder и strategy_router |
| Case studies | `case_studies.py` | SCARA proof points, подбираются по сигналам |
| `ANTHROPIC_API_KEY` | `.env` | Ключ для Claude Sonnet |

---

## Выходные данные

Proposal выводится в stdout в формате:

```
COVER LETTER:
<текст cover letter>

SUGGESTED RATE:
<ставка и обоснование>

STRATEGY NOTES:
<краткое обоснование угла>
```

Cover letter (без остального) автоматически копируется в буфер обмена (`pbcopy` / `xclip`).

---

## Агенты

| Агент | Файл | Роль |
|---|---|---|
| Agent 2 | `prompt_builder.py` | System prompt + user prompt, draft |
| Agent 3 | `critic.py` | Critique: word count, структура, claims |
| Agent 4 | `rewriter.py` | Rewrite по инструкциям Agent 3 |
| Validator | `validator.py` | Post-rewrite: word count ≤250, em dashes, opener |

Полные определения поведения — в `agents/agent2_drafter.md`, `agent3_critic.md`, `agent4_rewriter.md`.

---

## Флаги

| Флаг | Поведение |
|---|---|
| *(нет флагов)* | Полный пайплайн A2 → A3 → A4 |
| `--dry-run` | Только strategy_router, без API-вызовов |
| `--raw` | Только A2, без critique и rewrite |
| `--critique-only` | A2 + A3, вывести critique без rewrite |
| `--mark-applied` | UPDATE jobs SET applied=1 |
| `--outcome` | UPDATE jobs SET outcome=? |

---

## Код

| Файл | Роль |
|---|---|
| `skills/draft_proposal.py` | Исполняемый skill (sys.path + CLI wrapper) |
| `proposal-drafter/draft.py` | Основная логика: load, draft_for_job, mark_applied |
| `proposal-drafter/strategy_router.py` | Signals → угол предложения |
| `proposal-drafter/prompt_builder.py` | Agent 2 system prompt + user prompt |
| `proposal-drafter/critic.py` | Agent 3 system + critic prompt |
| `proposal-drafter/rewriter.py` | Agent 4 system + rewriter prompt |
| `proposal-drafter/api_client.py` | Claude Sonnet API (timeout: 90s) |
| `proposal-drafter/validator.py` | Post-rewrite валидация |
| `case_studies.py` | SCARA proof points |
