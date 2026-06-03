# AI Job Alerts

AI Job Alerts is an automated job-search pipeline that collects early-career job opportunities, filters them, ranks them with Claude, and emails the best matches.

The project is designed to run automatically every day through GitHub Actions.

## What it does

The pipeline:

1. Collects job postings from multiple public sources.
2. Filters out irrelevant roles using keyword-based rules.
3. Compares new jobs against a candidate profile.
4. Scores each job with Claude.
5. Sends an email digest with only the best matches.
6. Tracks already-seen jobs to avoid duplicate alerts.

## Main flow

```text
job_collector.py
        ↓
all_jobs.csv
        ↓
job_filter.py
        ↓
filtered_jobs.csv
        ↓
run_alerts.py
        ↓
claude_ranker.py
        ↓
emailer.py
        ↓
email alert
```

## Files

| File | Purpose |
|---|---|
| `job_collector.py` | Collects job postings from different job boards and company career pages. |
| `job_filter.py` | Filters collected jobs using keyword rules. |
| `claude_ranker.py` | Uses Claude to score jobs against the candidate profile. |
| `run_alerts.py` | Main pipeline runner. Checks new jobs, ranks them, emails good matches, and updates seen jobs. |
| `emailer.py` | Sends the email digest through Gmail SMTP. |
| `seen_store.py` | Manages already-seen job URLs. |
| `preseed_seen.py` | Utility script to pre-fill the seen jobs store. |
| `seen_jobs.json` | Stores already-seen job URLs to prevent duplicate alerts. |
| `.github/workflows/jobalerts.yml` | GitHub Actions workflow that runs the pipeline automatically. |
| `requirements.txt` | Python dependencies. |

## Private files

These files are intentionally not included in the repository:

| File | Reason |
|---|---|
| `.env` | Contains private API keys and email credentials. |
| `profile.txt` | Contains the private candidate profile. |
| `*.csv` | Generated job results. |
| `*.log` | Local logs. |
| `*.plist` | Local macOS scheduling files. |
| `program_calendar.py` | Local macOS scheduling helper. |

## Required GitHub Secrets

The GitHub Actions workflow needs these repository secrets:

| Secret | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key. |
| `GMAIL_ADDRESS` | Gmail address used to send alerts. |
| `GMAIL_APP_PASSWORD` | Gmail app password. |
| `PROFILE_TEXT` | Candidate profile used by Claude to rank jobs. |

## Claude API cost

This project uses the Claude API through Anthropic.

Using the Claude API may generate costs depending on Anthropic pricing, the selected model, and the number of jobs scored.

The project reduces unnecessary API calls by tracking already-seen jobs in `seen_jobs.json`.

## How to run locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
ANTHROPIC_API_KEY=your_api_key_here
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=your_gmail_app_password
```

Create a local `profile.txt` file with the candidate profile.

Then run:

```bash
python job_collector.py
python job_filter.py
python run_alerts.py
```

## How to run on GitHub Actions

The workflow runs automatically every day using GitHub Actions.

It can also be started manually from:

```text
GitHub repository → Actions → Daily job alerts → Run workflow
```

## Notes

Generated CSV files are not committed because they are recreated on each run.

The only persistent state file committed to the repository is `seen_jobs.json`, which prevents duplicate job alerts.
