"""
preseed_seen.py

One-shot helper: takes every URL from ranked_jobs.csv (the jobs Claude has
already scored) and writes them into seen_jobs.json. After running this,
run_alerts.py will treat all those jobs as "already seen" and only score
truly new postings on its next run - saving you the cost of re-ranking.

Run once, then never again:
    python3 preseed_seen.py
"""

import pandas as pd
import seen_store


def main():
    df = pd.read_csv("ranked_jobs.csv").fillna("")

    seen = seen_store.load_seen()
    before = len(seen)

    for url in df["url"]:
        if url:
            seen.add(url)

    seen_store.save_seen(seen)
    print(f"Pre-seeded seen_jobs.json with {len(seen) - before} new URLs.")
    print(f"Total URLs now marked as seen: {len(seen)}.")
    print("Next run_alerts.py run will only score genuinely new postings.")


if __name__ == "__main__":
    main()
