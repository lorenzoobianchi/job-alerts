"""
claude_ranker.py

Step 1 - the AI ranking layer.

The keyword filter (job_filter.py) is good at throwing OUT obviously-wrong jobs,
but it can't really judge whether a "Business Operations Associate" in some city
is a strong fit for YOU. Claude can. This script takes the ~300 jobs that
survived the keyword filter, sends each one to Claude together with your
profile, and gets back a fit score (0-100) plus a one-line reason.

Pipeline:
    python3 job_collector.py     # gather jobs        -> all_jobs.csv
    python3 job_filter.py        # cheap keyword cut  -> filtered_jobs.csv
    python3 claude_ranker.py     # smart AI ranking   -> ranked_jobs.csv

Output: ranked_jobs.csv, sorted best-fit first, with two new columns:
    ai_score    (0-100)
    ai_reason   (one line explaining the score)
"""

import os
import sys
import time
import json

import pandas as pd

# The official Anthropic SDK + dotenv (reads the .env file). Install once with:
#     pip install anthropic python-dotenv
try:
    import anthropic
except ImportError:
    print("The 'anthropic' package isn't installed yet.")
    print("Run:  pip install anthropic python-dotenv")
    sys.exit(1)

# Load the .env file sitting in this folder, so ANTHROPIC_API_KEY (and the
# Gmail vars) become available without touching the terminal or ~/.zshrc.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # If python-dotenv isn't installed, we just fall back to real env vars.
    pass


# ----------------------------
# CONFIG
# ----------------------------

INPUT_FILE = "filtered_jobs.csv"
OUTPUT_FILE = "ranked_jobs.csv"
PROFILE_FILE = "profile.txt"

# Haiku is the cheapest current model and is ideal for scoring/classification.
# At ~$1 per million input tokens, ranking 300 jobs costs only a few cents.
MODEL = "claude-haiku-4-5-20251001"

# Be polite to the API and stay well inside rate limits.
DELAY_BETWEEN_CALLS = 0.4

# How long a job description we send. Full descriptions waste tokens; the first
# part almost always contains the role summary and requirements.
MAX_DESCRIPTION_CHARS = 1500


# ----------------------------
# API KEY - read from the .env file
# ----------------------------
# Your API key is like a password: anyone who has it can spend your money.
#
# This script reads it from a file called ".env" in the same folder. Create it
# in VS Code (File -> New File -> name it exactly ".env") with this one line:
#
#     ANTHROPIC_API_KEY=sk-ant-...your-key...
#
# Notes:
#   - No quotes, no spaces around the = sign. Just KEY=value.
#   - The ".env" file must sit in the same folder as this script.
#   - NEVER share .env or put it on GitHub. Create a file named ".gitignore"
#     in the folder containing the single line:  .env

if not os.environ.get("ANTHROPIC_API_KEY"):
    print("No API key found.")
    print('Create a file named ".env" in this folder containing:')
    print('    ANTHROPIC_API_KEY=sk-ant-...your-key...')
    sys.exit(1)

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment


# ----------------------------
# PROMPT BUILDING
# ----------------------------

def load_profile():
    # On GitHub Actions the profile lives in a Secret called PROFILE_TEXT,
    # so we don't have to commit the file to the repo. Locally on the Mac,
    # the profile.txt file sits next to the script.
    profile_from_env = os.environ.get("PROFILE_TEXT")
    if profile_from_env:
        return profile_from_env

    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Could not find {PROFILE_FILE} and PROFILE_TEXT is not set.")
        sys.exit(1)


SYSTEM_PROMPT = """You are a career advisor scoring how well a single job fits a \
specific candidate. You will be given the candidate's profile and one job. \
Score the fit from 0 to 100, where:
- 90-100: excellent fit, candidate should apply now
- 70-89: strong fit, clearly worth applying
- 50-69: plausible fit with some gaps
- 30-49: weak fit, probably not worth the effort
- 0-29: poor fit or disqualifying mismatch (seniority, function, location, visa)

PRIORITIES, in this exact order (this overrides anything in the profile text):
1. COMPENSATION & COMPANY TIER. Top priority is high pay and prestigious \
employers where the candidate can build a strong career: big tech (Google, \
Meta, Microsoft, Amazon, Apple, Nvidia), top fintech/payments (Stripe, Adyen, \
Wise, Revolut, Klarna), MBB consulting, top trading firms (Optiver, IMC, \
Jane Street, Citadel, Flow Traders), top AI labs (OpenAI, Anthropic, Mistral), \
unicorns and Series C/D scale-ups with strong funding (Databricks, Datadog, \
MongoDB, Snowflake, Bending Spoons, Picnic, n8n, Parloa, Lovable, Synthesia, \
ElevenLabs). Score these HIGH even if the role/function is just decent.
2. ROLE & LEVEL. Junior/grad/analyst/associate/APM/PM new grad. Reject \
senior, lead, principal, staff, director, head-of.
3. FUNCTION. Product, strategy, operations, data, business analyst, \
consulting. Avoid pure engineering, pure sales, support, HR, legal.
4. LOCATION. Amsterdam is the #1 target city - give Amsterdam-based jobs an \
explicit boost in the score. Other European hubs (London, Berlin, Dublin, \
Paris, Zurich, Milan) are also preferred. A top-tier US/UK company can still \
score high if the role is great, but never above an equivalent Amsterdam role.
5. INDUSTRY INTEREST. Travel/mobility/logistics is a NICE-TO-HAVE bonus, NOT \
a primary criterion. A high-paying fintech or AI role beats a mediocre travel \
role every time.

Respond with ONLY a JSON object, no other text, no markdown fences:
{"score": <integer 0-100>, "reason": "<one short sentence>"}"""


def build_job_text(row):
    description = str(row.get("description", ""))[:MAX_DESCRIPTION_CHARS]
    return (
        f"Company: {row.get('company', '')}\n"
        f"Title: {row.get('title', '')}\n"
        f"Location: {row.get('location', '')}\n"
        f"Source: {row.get('source', '')}\n"
        f"Description (truncated): {description}"
    )


def score_one_job(profile_text, job_text):
    """Send one job to Claude and return (score, reason)."""
    message = client.messages.create(
        model=MODEL,
        max_tokens=150,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"CANDIDATE PROFILE:\n{profile_text}\n\n"
                f"JOB TO SCORE:\n{job_text}"
            ),
        }],
    )

    raw = message.content[0].text.strip()

    # Strip accidental code fences just in case.
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        parsed = json.loads(raw)
        score = int(parsed.get("score", 0))
        reason = str(parsed.get("reason", "")).strip()
        return score, reason
    except (json.JSONDecodeError, ValueError):
        # If Claude ever returns something unparseable, don't crash the run.
        return -1, "Could not parse AI response"


# ----------------------------
# MAIN
# ----------------------------

def rank_jobs():
    profile_text = load_profile()
    df = pd.read_csv(INPUT_FILE).fillna("")

    total = len(df)
    print(f"Ranking {total} jobs with {MODEL}...\n")

    scores = []
    reasons = []

    for i, (_, row) in enumerate(df.iterrows(), start=1):
        job_text = build_job_text(row)
        try:
            score, reason = score_one_job(profile_text, job_text)
        except Exception as error:
            # Network hiccup, rate limit, etc. - record and keep going.
            print(f"  [{i}/{total}] error: {error}")
            score, reason = -1, f"API error: {error}"

        scores.append(score)
        reasons.append(reason)

        # Light progress output so you can see it working.
        if i % 10 == 0 or i == total:
            print(f"  scored {i}/{total}")

        time.sleep(DELAY_BETWEEN_CALLS)

    df["ai_score"] = scores
    df["ai_reason"] = reasons

    # Sort best fit first; unparseable rows (-1) sink to the bottom.
    df = df.sort_values(by="ai_score", ascending=False)
    df.to_csv(OUTPUT_FILE, index=False)

    print("\n==============================")
    print(f"Ranked {total} jobs -> {OUTPUT_FILE}")
    print("==============================\n")

    print("Top 15 by AI fit score:\n")
    for _, job in df.head(15).iterrows():
        print(f"[{job['ai_score']}] {job['company']} - {job['title']} ({job['location']})")
        print(f"      {job['ai_reason']}")
        print(f"      {job.get('url', '')}\n")


if __name__ == "__main__":
    rank_jobs()
