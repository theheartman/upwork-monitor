# Skill: Upwork Job Search

**What it does:** Запускает Apify-актор, скачивает список вакансий с Upwork по ключевым словам, нормализует и оценивает каждую.

**Trigger:** вызывается напрямую через `skills/upwork_job_search.py` или из `main.py → run_once()`.

---

## Вызов

```bash
# Стандартный прогон (keywords из config.py)
python skills/upwork_job_search.py

# Кастомные ключевые слова
python skills/upwork_job_search.py --keywords "Clay CRM" "GTM engineer"

# Только primary или только secondary
python skills/upwork_job_search.py --primary-only
python skills/upwork_job_search.py --secondary-only

# Изменить лимит
python skills/upwork_job_search.py --limit 50

# Без Telegram-уведомлений
python skills/upwork_job_search.py --no-alerts

# Dry-run: score без записи в БД
python skills/upwork_job_search.py --dry-run
```

---

## Flow

```
Keywords (config.py)
    │
    ▼
apify_client.run_actor()          # запуск актора, ожидание, скачивание
    │
    ▼
normalizer.normalize_batch()      # маппинг сырых полей → Job dataclass
    │
    ▼
dedup.is_new()                    # проверка по job_id — новая или уже видели
    │
    ├── уже видели → update_applicants() и пропустить
    └── новая
            │
            ▼
        scorer.score_job()        # оценка 0–100 + список сигналов
            │
            ▼
        dedup.insert_job()        # сохранить в SQLite
            │
            ▼
        alerts.send_job_alert()   # Telegram-уведомление (если score ≥ 60)
```

---

## Входные данные

| Параметр | Источник | Описание |
|---|---|---|
| `PRIMARY_KEYWORDS` | `config.py` | 4 ключевых слова, запрос с лимитом `JOBS_PER_KEYWORD` (200) |
| `SECONDARY_KEYWORDS` | `config.py` | 7 ключевых слов, запрос с лимитом `JOBS_PER_KEYWORD_SECONDARY` (75) |
| `APIFY_ACTOR_ID` | `.env` | ID актора (`flash_mage~upwork`) |
| `APIFY_TOKEN` | `.env` | API-токен Apify |

**Текущие ключевые слова:**

Primary:
- Clay enrichment
- Clay CRM
- GTM engineer
- RevOps automation

Secondary:
- CRM automation specialist
- Clay automation
- HubSpot automation consultant
- outbound enrichment
- sales automation architect
- CRM data cleanup
- lead generation automation

---

## Выходные данные

Каждая новая вакансия сохраняется в SQLite (`db/jobs.db`, таблица `jobs`) со следующими полями:

| Поле | Описание |
|---|---|
| `job_id` | URL вакансии (уникальный ключ дедупликации) |
| `title` | Название |
| `description` | Описание |
| `score` | 0–100 |
| `tier` | `APPLY_NOW` / `STRONG_FIT` / `MAYBE` / `SKIP` |
| `signals` | JSON-массив сработавших сигналов |
| `hourly_min/max` | Ставка |
| `fixed_amount` | Фиксированный бюджет |
| `first_seen_at` | Timestamp первого обнаружения |
| `alerted` | Было ли отправлено уведомление |
| `applied` | Подал ли заявку |

---

## Scoring tiers

| Score | Tier | Действие |
|---|---|---|
| 80–100 | `APPLY_NOW` | Уведомление, подать в течение 1 часа |
| 60–79 | `STRONG_FIT` | Уведомление, подать в течение 4 часов |
| 40–59 | `MAYBE` | Без уведомления |
| 0–39 | `SKIP` | Без уведомления |
| 0 (budget gate) | — | Не сохраняется |

---

## Конфигурация

Все параметры меняются в `config.py` без правок логики:

```python
JOBS_PER_KEYWORD = 200           # лимит для primary keywords
JOBS_PER_KEYWORD_SECONDARY = 75  # лимит для secondary keywords
SCORE_APPLY_NOW = 80
SCORE_STRONG_FIT = 60
RUN_TIMES = "07:30,15:00"        # расписание (Warsaw timezone)
```

---

## Error handling

**Maintenance retries:** если актор отвечает `FAILED` со статусом "actor under maintenance" — автоматически 3 попытки с паузой 90 секунд между ними (`apify_client.py → _run_batch_with_retry()`).

**Batching:** если ключевых слов больше 5, актор запускается несколькими батчами по 5 слов (`MAX_KEYWORDS_PER_RUN = 5`).

---

## Код

| Файл | Роль |
|---|---|
| `main.py` | Оркестратор, запуск по расписанию |
| `apify_client.py` | HTTP-запросы к Apify API, polling, retry-логика |
| `normalizer.py` | Маппинг сырых JSON-полей актора → `Job` dataclass |
| `scorer.py` | Скоринг 0–100 с budget gate, domain filter, depth signals |
| `dedup.py` | SQLite — проверка дублей, вставка, update applicants |
| `alerts.py` | Telegram-уведомления по каждой вакансии и сводка по прогону |
