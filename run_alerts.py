"""
run_alerts.py

Each run:
  1. reads filtered_jobs.csv
  2. keeps only jobs not seen before
  3. asks Claude to score new jobs
  4. emails the ones Claude rates highly
  5. remembers jobs only if processing/email succeeded
"""

import sys
import time
import pandas as pd

import seen_store
import emailer

try:
    import claude_ranker
except SystemExit:
    print("Fix the API key setup and try again.")
    sys.exit(1)


INPUT_FILE = "filtered_jobs.csv"
EMAIL_SCORE_THRESHOLD = 75


def main():
    try:
        df = pd.read_csv(INPUT_FILE).fillna("")
    except FileNotFoundError:
        print(f"Missing {INPUT_FILE}. Run job_collector.py and job_filter.py first.")
        sys.exit(1)

    new_jobs, seen = seen_store.split_new_and_seen(df)
    print(f"{len(df)} jobs in file, {len(new_jobs)} are new.\n")

    if new_jobs.empty:
        print("Nothing new since last run. No email, no API cost.")
        return

    profile_text = claude_ranker.load_profile()
    high_fit = []
    had_api_errors = False

    for i, (_, row) in enumerate(new_jobs.iterrows(), start=1):
        job_text = claude_ranker.build_job_text(row)

        try:
            score, reason = claude_ranker.score_one_job(profile_text, job_text)
        except Exception as error:
            print(f"  [{i}/{len(new_jobs)}] error: {error}")
            score, reason = -1, f"API error: {error}"
            had_api_errors = True

        company = row.get("company", "")
        title = row.get("title", "")

        print(f"  [{i}/{len(new_jobs)}] {score} - {company}: {title}")

        if score >= EMAIL_SCORE_THRESHOLD:
            description = str(row.get("description", "")).lower()
            source = str(row.get("source", "")).lower()

            if source == "apm list" and "not yet open" in description:
                print("       (skipping email: APM program not yet open)")
            else:
                high_fit.append({
                    "company": company,
                    "title": title,
                    "location": row.get("location", ""),
                    "ai_score": score,
                    "ai_reason": reason,
                    "url": row.get("url", ""),
                })

        time.sleep(claude_ranker.DELAY_BETWEEN_CALLS)

    high_fit.sort(key=lambda j: j["ai_score"], reverse=True)

    print()

    email_ok = True

    if high_fit:
        email_ok = emailer.send_job_digest(high_fit)
    else:
        print(f"No new jobs scored >= {EMAIL_SCORE_THRESHOLD}. No email this run.")

    if had_api_errors:
        print("\nSome API calls failed. Not marking jobs as seen, so they can be retried.")
        return

    if not email_ok:
        print("\nEmail failed. Not marking jobs as seen, so they can be retried.")
        return

    seen = seen_store.mark_seen(seen, new_jobs)
    seen_store.save_seen(seen)
    print(f"\nRemembered {len(new_jobs)} new job(s). Total seen: {len(seen)}.")


if __name__ == "__main__":
    main()
