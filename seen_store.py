"""
seen_store.py

Remembers which jobs have already been processed, so each run only sends NEW
jobs to Claude. This is what keeps the cost tiny after the first run: the first
run scores ~300 jobs (~0.80 EUR), every run after that scores only the handful
of genuinely new postings (fractions of a cent).

How it works: each job's URL is its fingerprint. We store the set of seen URLs
in a small JSON file. No database needed.
"""

import os
import json

SEEN_FILE = "seen_jobs.json"


def load_seen():
    """Return the set of job URLs we've already processed."""
    if not os.path.exists(SEEN_FILE):
        return set()
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, ValueError):
        # Corrupted file -> start fresh rather than crash.
        return set()


def save_seen(seen_urls):
    """Persist the set of seen URLs back to disk."""
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen_urls), f, indent=2)


def split_new_and_seen(df):
    """Given a dataframe of jobs, return (new_jobs_df, seen_set).

    A job is 'new' if its URL isn't in the seen file yet. Jobs with no URL are
    treated as new (better to show them once than silently drop them).
    """
    seen = load_seen()
    is_new = df["url"].apply(lambda u: (not u) or (u not in seen))
    return df[is_new].copy(), seen


def mark_seen(seen_set, df):
    """Add all URLs from df to the seen set and return it."""
    for url in df["url"]:
        if url:
            seen_set.add(url)
    return seen_set
