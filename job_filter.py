import re
import pandas as pd


# ----------------------------
# CONFIG
# ----------------------------

INPUT_FILE = "all_jobs.csv"
OUTPUT_FILE = "filtered_jobs.csv"

# Keep a job if its score reaches this threshold.
MIN_SCORE = 50


# ----------------------------
# KEYWORD LISTS
# ----------------------------

EUROPE_KEYWORDS = [
    "london", "united kingdom", "uk", "england", "scotland",
    "amsterdam", "netherlands", "rotterdam",
    "berlin", "munich", "hamburg", "germany",
    "paris", "france",
    "zurich", "geneva", "switzerland",
    "milan", "rome", "italy",
    "madrid", "barcelona", "spain",
    "dublin", "ireland",
    "copenhagen", "denmark",
    "stockholm", "sweden",
    "lisbon", "porto", "portugal",
    "warsaw", "poland",
    "prague", "czech",
    "vienna", "austria",
    "brussels", "belgium",
    "helsinki", "finland",
    "oslo", "norway",
    "europe", "emea", "remote - europe", "remote europe",
]

# Cities Lorenzo most wants (extra weight).
TOP_CITY_KEYWORDS = [
    "amsterdam", "london", "berlin", "paris",
    "zurich", "milan", "madrid", "barcelona", "dublin",
]

# Strong title matches -> these are the roles to chase.
GOOD_ROLE_KEYWORDS = [
    "associate product manager", "apm",
    "junior product manager", "product manager",
    "product analyst", "product operations", "product ops", "product strategy",
    "business analyst", "strategy analyst", "strategic analyst",
    "commercial analyst", "business operations", "business ops",
    "operations analyst", "operations associate", "operations strategy",
    "gtm strategy", "gtm operations", "go-to-market",
    "marketplace operations", "process improvement", "process analyst",
    "data analyst", "business intelligence", "bi analyst",
    "analytics analyst", "insights analyst",
    "graduate program", "graduate scheme", "graduate analyst",
    "rotational", "new grad", "early career", "associate program",
    "revenue management", "network planning", "route planning",
    "transport planning", "mobility operations", "logistics analyst",
    "supply chain analyst", "fleet operations", "demand planning",
    "customer experience analyst", "travel operations",
]

# Title matches that should knock a job out. Each is matched as a whole word /
# phrase, so "manager," will not accidentally match "Manager of Product".
BAD_ROLE_KEYWORDS = [
    # Too senior
    "senior", "sr", "lead", "director", "head", "principal",
    "staff", "vp", "vice president", "chief", "leader", "leadership",
    "manager ii", "manager iii", "group manager",
    # Too technical / pure engineering
    "software engineer", "backend engineer", "frontend engineer",
    "front end engineer", "full stack engineer", "fullstack engineer",
    "devops", "site reliability", "sre", "machine learning engineer",
    "ml engineer", "data engineer", "security engineer", "cloud engineer",
    "infrastructure engineer", "platform engineer", "qa engineer",
    "technical support", "it support", "support technician",
    "support engineer", "field engineer",
    # Not aligned
    "account executive", "account manager", "sales development",
    "business development representative", "sdr", "bdr",
    "customer support", "customer success", "client partner",
    "people consultant", "people partner", "recruiter",
    "talent acquisition", "legal counsel", "internal auditor",
    "tax advisory", "hr business partner", "paralegal", "accountant",
]

# Companies / industries Lorenzo specifically wants.
PREFERRED_COMPANY_KEYWORDS = [
    # Big tech (top tier, top pay)
    "google", "meta", "facebook", "microsoft", "amazon", "apple", "nvidia",
    "linkedin", "tiktok", "bytedance", "salesforce", "oracle", "ibm",
    # Top fintech / payments
    "stripe", "adyen", "wise", "revolut", "klarna", "mollie", "ramp",
    "brex", "plaid", "checkout", "n26", "monzo", "trade republic",
    "robinhood", "coinbase",
    # Trading (very high comp)
    "optiver", "imc", "jane street", "citadel", "flow traders", "akuna",
    "hudson river", "drw", "two sigma", "de shaw", "g-research",
    # Top AI labs
    "openai", "anthropic", "mistral", "perplexity", "elevenlabs", "cohere",
    "scale ai", "huggingface", "deepmind", "xai",
    # Top SaaS / dev tools / infra
    "databricks", "datadog", "mongodb", "snowflake", "cloudflare",
    "gitlab", "github", "atlassian", "asana", "figma", "notion", "miro",
    "celonis", "n8n", "parloa", "lovable", "synthesia", "encord",
    "vercel", "supabase", "ramp", "personio", "hashicorp",
    # Top scale-ups (consumer / marketplace / well funded)
    "bending spoons", "picnic", "spotify", "shopify", "canva", "klaviyo",
    # Travel / mobility / logistics (bonus, not primary)
    "booking", "airbnb", "skyscanner", "expedia", "getyourguide",
    "trainline", "omio", "hostelworld", "amadeus", "uber", "bolt",
    "freenow", "flix", "flixbus", "lime", "dott", "tier", "voi",
    "deliveroo", "doordash", "flexport", "sennder", "forto",
    # Consulting (top tier)
    "mckinsey", "bain", "bcg", "boston consulting",
]

# Words that mark a posting as travel / mobility / logistics flavored.
INDUSTRY_INTEREST_KEYWORDS = [
    "travel", "tourism", "airline", "aviation", "mobility",
    "transport", "logistics", "supply chain", "marketplace",
]


# ----------------------------
# HELPERS
# ----------------------------

def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).lower().strip()


def contains_phrase(text, keyword):
    """Match keyword as a whole word/phrase, not a loose substring.

    This stops bugs like 'sr' matching 'desire' or 'apm' matching 'champion'.
    """
    pattern = r"\b" + re.escape(keyword) + r"\b"
    return re.search(pattern, text) is not None


def contains_any(text, keywords):
    text = clean_text(text)
    return any(contains_phrase(text, k) for k in keywords)


# ----------------------------
# SCORING
# ----------------------------

def calculate_score(row):
    title = clean_text(row.get("title", ""))
    location = clean_text(row.get("location", ""))
    company = clean_text(row.get("company", ""))
    description = clean_text(row.get("description", ""))
    source = clean_text(row.get("source", ""))

    full_text = f"{title} {location} {company} {description}"

    score = 0
    reasons = []

    # --- APM List has its own logic (title is always "APM Program") ---
    if source == "apm list":
        if "closed" in description:
            return -100, "APM program closed for the cycle"
        if "paused" in description:
            return -100, "APM program paused"
        if "not yet open" in description:
            score += 70
            reasons.append("APM program – not yet open (track it)")
        else:  # "Open"
            score += 95
            reasons.append("APM program – currently OPEN")
        # Preferred company bonus still applies to APM List rows.
        if contains_any(company, PREFERRED_COMPANY_KEYWORDS):
            score += 10
            reasons.append("Preferred company")
        return score, "; ".join(reasons)

    # --- Everything else (Greenhouse, Lever, Ashby, Remotive, etc.) ---

    # Hard exclusion: a bad title kills the job outright.
    if contains_any(title, BAD_ROLE_KEYWORDS):
        return -100, "Excluded: senior / technical / non-aligned role"

    # Title relevance (most important signal).
    if contains_any(title, GOOD_ROLE_KEYWORDS):
        score += 45
        reasons.append("Relevant role title")
    elif contains_any(description, GOOD_ROLE_KEYWORDS):
        score += 15
        reasons.append("Relevant role in description")

    # Geography – weighted so Europe genuinely beats a US duplicate.
    # Amsterdam gets an extra bonus: it's the #1 target city and matches the
    # 30% tax ruling strategy.
    if "amsterdam" in location:
        score += 45
        reasons.append("Amsterdam (top priority city)")
    elif contains_any(location, TOP_CITY_KEYWORDS):
        score += 35
        reasons.append("Top target city")
    elif contains_any(location, EUROPE_KEYWORDS):
        score += 25
        reasons.append("European location")

    # Preferred company / industry. Heavily weighted: top companies are the
    # primary criterion, not the industry sector.
    if contains_any(company, PREFERRED_COMPANY_KEYWORDS):
        score += 25
        reasons.append("Top-tier company (high pay / prestige)")

    # Travel / mobility / logistics flavor - small bonus, not a main driver.
    if contains_any(full_text, INDUSTRY_INTEREST_KEYWORDS):
        score += 5
        reasons.append("Travel / mobility / logistics bonus")

    return score, "; ".join(reasons)


# ----------------------------
# MAIN FILTER
# ----------------------------

def filter_jobs():
    df = pd.read_csv(INPUT_FILE).fillna("")

    scored = df.apply(calculate_score, axis=1)
    df["filter_score"] = scored.apply(lambda x: x[0])
    df["filter_reasons"] = scored.apply(lambda x: x[1])

    filtered = df[df["filter_score"] >= MIN_SCORE].copy()
    filtered = filtered.sort_values(by="filter_score", ascending=False)

    filtered.to_csv(OUTPUT_FILE, index=False)

    print("==============================")
    print(f"Input jobs:    {len(df)}")
    print(f"Filtered jobs: {len(filtered)}")
    print(f"File created:  {OUTPUT_FILE}")
    print("==============================\n")

    print("Top 20 filtered jobs:\n")
    for _, job in filtered.head(20).iterrows():
        print("-" * 60)
        print("Score:   ", job.get("filter_score"))
        print("Source:  ", job.get("source"))
        print("Company: ", job.get("company"))
        print("Title:   ", job.get("title"))
        print("Location:", job.get("location"))
        print("Reasons: ", job.get("filter_reasons"))
        print("URL:     ", job.get("url"))


if __name__ == "__main__":
    filter_jobs()
