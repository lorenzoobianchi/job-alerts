import time
import hashlib
import requests
import pandas as pd
from bs4 import BeautifulSoup


# ----------------------------
# CONFIG
# ----------------------------

OUTPUT_FILE = "all_jobs.csv"
REQUEST_DELAY_SECONDS = 0.6
THE_MUSE_PAGE_LIMIT = 20

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


GREENHOUSE_COMPANIES = [
    # Fintech / payments / financial infrastructure
    "adyen",
    "stripe",
    "checkout",
    "checkoutcom",
    "plaid",
    "monzo",
    "n26",
    "mollie",
    "bunq",
    "sumup",
    "coinbase",
    "kraken",
    "bitpanda",
    "trade-republic",
    "traderepublic",

    # Data / cloud / SaaS
    "databricks",
    "datadog",
    "mongodb",
    "gitlab",
    "snowflake",
    "elastic",
    "confluent",
    "cloudflare",
    "snyk",
    "sentinelone",
    "hashicorp",
    "miro",
    "typeform",
    "personio",
    "celonis",

    # AI / high-growth tech
    "openai",
    "anthropic",
    "perplexity",
    "mistral",
    "huggingface",
    "deepmind",
    "scaleai",
    "cohere",
    "elevenlabs",
    "cursor",
    "replit",

    # Travel / mobility / marketplaces
    "airbnb",
    "booking",
    "getyourguide",
    "skyscanner",
    "omio",
    "trainline",
    "bolt",
    "lime",
    "deliveroo",
    "doordash",
    "uber",

    # Logistics / transport / supply chain
    "flexport",
    "sennder",
    "forto",
    "project44",
    "maersk",
    "dhl",

    # Consulting / strategic tech
    "bcg",
    "mckinsey",
    "bain",
    "accenture",

    # Additional premium scale-ups (high pay / prestige)
    "ramp",
    "brex",
    "wise",
    "revolut",
    "klarna",
    "robinhood",
    "rippling",
    "carta",
    "klaviyo",
    "asana",
    "atlassian",
    "github",
    "vercel",
    "supabase",
    "n8n",
    "synthesia",
    "n8nio",
]


LEVER_COMPANIES = [
    # Big tech / consumer tech
    "spotify",
    "netflix",
    "figma",
    "notion",
    "canva",
    "zapier",
    "loom",
    "dropbox",

    # AI / high-growth startups
    "openai",
    "anthropic",
    "mistral",
    "perplexity",
    "huggingface",
    "scaleai",
    "cohere",
    "elevenlabs",
    "cursor",
    "replit",
    "runway",
    "synthesia",

    # Fintech / business software
    "ramp",
    "brex",
    "mercury",
    "deel",
    "remote",
    "rippling",
    "airwallex",
    "wise",
    "revolut",
    "klarna",

    # Trading / high compensation
    "optiver",
    "flowtraders",
    "jumptrading",
    "citadel",
    "janestreet",
    "imc",
    "akuna",

    # Travel / mobility / logistics
    "skyscanner",
    "omio",
    "trainline",
    "flixbus",
    "tier",
    "voi",
    "bolt",
    "lime",
    "getyourguide",
]


ASHBY_COMPANIES = [
    # AI / frontier tech
    "perplexity",
    "anthropic",
    "mistral",
    "openai",
    "elevenlabs",
    "cursor",
    "linear",
    "vercel",
    "replit",
    "runway",
    "synthesia",
    "deepgram",
    "modal",
    "together-ai",
    "together",
    "fireworks-ai",
    "fireworks",

    # SaaS / infra / data
    "watershed",
    "ramp",
    "mercury",
    "brex",
    "deel",
    "remote",
    "rippling",
    "airwallex",
    "linear",
    "notion",
    "figma",
    "vercel",
    "supabase",
    "clickhouse",
    "grafana",
    "posthog",

    # Fintech / finance
    "monzo",
    "n26",
    "mollie",
    "trade-republic",
    "traderepublic",
    "bitpanda",
    "kraken",

    # Travel / mobility / transport
    "airbnb",
    "getyourguide",
    "omio",
    "bolt",
    "lime",
    "sennder",
    "flexport",
]


# ----------------------------
# WORKDAY COMPANIES
# ----------------------------
# Workday URLs have three parts that must each be correct:
#   tenant       -> first label of the host (e.g. "visa" in visa.wd5.myworkdayjobs.com)
#   data_center  -> wd1 / wd3 / wd5 / wd12 ... (differs per company, cannot be guessed)
#   site         -> the career-site path segment (e.g. "Visa", "External_Career_Site")
#
# Each entry below was verified from the company's live careers URL.
# To add a company: open its careers page, look at the URL, and copy the three
# parts. If a company returns 0 jobs or an error, the site path is usually wrong.
#
# Format: (label, tenant, data_center, site)
WORKDAY_COMPANIES = [
    # --- Tech / payments / enterprise (verified hosts) ---
    ("Visa",        "visa",       "wd5",   "Visa"),
    ("Salesforce",  "salesforce", "wd12",  "External_Career_Site"),
    ("NVIDIA",      "nvidia",     "wd5",   "NVIDIAExternalCareerSite"),
    ("Workday",     "workday",    "wd5",   "Workday"),
    ("Santander",   "santander",  "wd3",   "SantanderCareers"),
    ("Philips",     "philips",    "wd3",   "jobs-and-careers"),

    # --- Travel / mobility / tourism (your core interest area) ---
    ("Amadeus",     "amadeus",    "wd502", "jobs"),
    ("Expedia",     "expedia",    "wd108", "search"),

    # --- To verify on your Mac (open the careers page, confirm the 3 parts) ---
    # The data_center and site below are best guesses and may need fixing.
    # If a company returns 0 jobs or "Bad response", the site path is wrong.
    # ("Uber",        "uber",       "wd5",   "External"),
    # ("Booking",     "booking",    "wd1",   "External"),
    # ("SAP",         "sap",        "wd3",   "SAP_SuccessFactors_Careers"),
    # ("ServiceNow",  "servicenow", "wd1",   "External"),
]


# ----------------------------
# HELPERS
# ----------------------------

def clean_html(html_text):
    if not html_text:
        return ""
    return BeautifulSoup(str(html_text), "html.parser").get_text(" ", strip=True)


def safe_get(url, timeout=20):
    try:
        response = requests.get(url, timeout=timeout, headers=REQUEST_HEADERS)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as error:
        return error


def make_job_id(job):
    raw = f"{job.get('source', '')}|{job.get('company', '')}|{job.get('title', '')}|{job.get('location', '')}|{job.get('url', '')}"
    return hashlib.md5(raw.lower().encode("utf-8")).hexdigest()


def remove_duplicates(jobs):
    unique = {}

    for job in jobs:
        url = str(job.get("url", "")).strip().lower()
        key = url if url else make_job_id(job)
        unique[key] = job

    return list(unique.values())


def normalize_job(job):
    return {
        "source": job.get("source", ""),
        "company": job.get("company", ""),
        "title": job.get("title", ""),
        "location": job.get("location", ""),
        "team": job.get("team", ""),
        "commitment": job.get("commitment", ""),
        "url": job.get("url", ""),
        "description": job.get("description", ""),
    }


# ----------------------------
# GREENHOUSE
# ----------------------------

def collect_greenhouse_jobs(company_name):
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_name}/jobs?content=true"
    response = safe_get(url, timeout=20)

    if isinstance(response, Exception):
        print(f"[Greenhouse] Error for {company_name}: {response}")
        return []

    jobs = response.json().get("jobs", [])
    results = []

    for job in jobs:
        results.append(normalize_job({
            "source": "Greenhouse",
            "company": company_name,
            "title": job.get("title", ""),
            "location": job.get("location", {}).get("name", ""),
            "team": ", ".join([department.get("name", "") for department in job.get("departments", [])]),
            "commitment": "",
            "url": job.get("absolute_url", ""),
            "description": clean_html(job.get("content", "")),
        }))

    return results


def collect_all_greenhouse_jobs():
    all_jobs = []

    for company in GREENHOUSE_COMPANIES:
        print(f"Collecting Greenhouse jobs from {company}...")
        jobs = collect_greenhouse_jobs(company)
        all_jobs.extend(jobs)
        print(f"  Found {len(jobs)} jobs")
        time.sleep(REQUEST_DELAY_SECONDS)

    return all_jobs


# ----------------------------
# LEVER
# ----------------------------

def collect_lever_jobs(company_name):
    url = f"https://api.lever.co/v0/postings/{company_name}?mode=json"
    response = safe_get(url, timeout=20)

    if isinstance(response, Exception):
        print(f"[Lever] Error for {company_name}: {response}")
        return []

    jobs = response.json()
    results = []

    for job in jobs:
        categories = job.get("categories", {}) or {}
        description = " ".join([
            job.get("descriptionPlain", "") or "",
            job.get("additionalPlain", "") or "",
        ]).strip()

        results.append(normalize_job({
            "source": "Lever",
            "company": company_name,
            "title": job.get("text", ""),
            "location": categories.get("location", ""),
            "team": categories.get("team", ""),
            "commitment": categories.get("commitment", ""),
            "url": job.get("hostedUrl", ""),
            "description": description,
        }))

    return results


def collect_all_lever_jobs():
    all_jobs = []

    for company in LEVER_COMPANIES:
        print(f"Collecting Lever jobs from {company}...")
        jobs = collect_lever_jobs(company)
        all_jobs.extend(jobs)
        print(f"  Found {len(jobs)} jobs")
        time.sleep(REQUEST_DELAY_SECONDS)

    return all_jobs


# ----------------------------
# ASHBY
# ----------------------------

def collect_ashby_jobs(company_name):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{company_name}"
    response = safe_get(url, timeout=20)

    if isinstance(response, Exception):
        print(f"[Ashby] Error for {company_name}: {response}")
        return []

    jobs = response.json().get("jobs", [])
    results = []

    for job in jobs:
        location = job.get("location", "")

        if not location and job.get("address"):
            location = job["address"].get("postalAddress", {}).get("addressLocality", "")

        results.append(normalize_job({
            "source": "Ashby",
            "company": company_name,
            "title": job.get("title", ""),
            "location": location,
            "team": job.get("department", ""),
            "commitment": job.get("employmentType", ""),
            "url": job.get("jobUrl", ""),
            "description": job.get("descriptionPlain", "") or clean_html(job.get("descriptionHtml", "")),
        }))

    return results


def collect_all_ashby_jobs():
    all_jobs = []

    for company in ASHBY_COMPANIES:
        print(f"Collecting Ashby jobs from {company}...")
        jobs = collect_ashby_jobs(company)
        all_jobs.extend(jobs)
        print(f"  Found {len(jobs)} jobs")
        time.sleep(REQUEST_DELAY_SECONDS)

    return all_jobs


# ----------------------------
# WORKDAY
# ----------------------------

def collect_workday_jobs(label, tenant, data_center, site):
    """Collect jobs from one Workday tenant.

    Workday's public job feed is a POST endpoint that returns JSON in pages.
    We page through it politely and stop when there are no more results.
    """
    base = f"https://{tenant}.{data_center}.myworkdayjobs.com"
    list_url = f"{base}/wday/cxs/{tenant}/{site}/jobs"

    # Workday is picky: it wants JSON headers and a Referer that looks like
    # a real visit to the career site, or it returns an error.
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": REQUEST_HEADERS["User-Agent"],
        "Referer": f"{base}/en-US/{site}",
    }

    results = []
    offset = 0
    page_size = 20

    while True:
        payload = {
            "appliedFacets": {},
            "limit": page_size,
            "offset": offset,
            "searchText": "",
        }

        try:
            response = requests.post(
                list_url, json=payload, headers=headers, timeout=25
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as error:
            print(f"[Workday] Error for {label}: {error}")
            break
        except ValueError as error:
            # Got HTML instead of JSON -> usually a wrong site path or a block.
            print(f"[Workday] Bad response for {label}: {error}")
            break

        postings = data.get("jobPostings", [])
        if not postings:
            break

        for job in postings:
            # externalPath looks like "/job/Location/Title_JR123"; the full
            # apply URL is the career site plus that path.
            external_path = job.get("externalPath", "")
            job_url = f"{base}/en-US/{site}{external_path}" if external_path else ""

            results.append(normalize_job({
                "source": "Workday",
                "company": label,
                "title": job.get("title", ""),
                "location": job.get("locationsText", ""),
                "team": "",
                "commitment": "",
                "url": job_url,
                # The list endpoint has no description; we keep the short
                # "bulletFields" info so the filter still has something to read.
                "description": " ".join(job.get("bulletFields", []) or []),
            }))

        total = data.get("total", 0)
        offset += page_size
        if offset >= total:
            break

        time.sleep(REQUEST_DELAY_SECONDS)

    return results


def collect_all_workday_jobs():
    all_jobs = []

    for label, tenant, data_center, site in WORKDAY_COMPANIES:
        print(f"Collecting Workday jobs from {label}...")
        jobs = collect_workday_jobs(label, tenant, data_center, site)
        all_jobs.extend(jobs)
        print(f"  Found {len(jobs)} jobs")
        time.sleep(REQUEST_DELAY_SECONDS)

    return all_jobs


def test_workday_tenant(tenant, data_center, site):
    """Quick check for a single Workday company before adding it to the list.

    Run from a Python shell on your Mac:
        import job_collector as jc
        jc.test_workday_tenant("uber", "wd5", "External")

    Prints how many jobs came back and the first few titles, so you can confir
    the three URL parts are correct before committing them to WORKDAY_COMPANIES.
    """
    jobs = collect_workday_jobs(tenant, tenant, data_center, site)
    print(f"\nTenant '{tenant}' / site '{site}' on {data_center}: {len(jobs)} jobs")
    for job in jobs[:5]:
        print(f"  - {job['title']}  ({job['location']})")
    if not jobs:
        print("  No jobs -> the site path or data_center is probably wrong.")
    return jobs


# ----------------------------
# APM LIST
# ----------------------------

def collect_apm_list_jobs():
    url = "https://apmlist.com/"
    response = safe_get(url, timeout=20)

    if isinstance(response, Exception):
        print(f"[APM List] Error: {response}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table")
    results = []

    for table in tables:
        rows = table.find_all("tr")

        for row in rows[1:]:
            cells = row.find_all("td")

            if len(cells) < 2:
                continue

            company = cells[0].get_text(strip=True)
            status = cells[1].get_text(strip=True)
            link_tag = row.find("a", href=True)
            job_url = link_tag["href"] if link_tag else ""

            results.append(normalize_job({
                "source": "APM List",
                "company": company,
                "title": "APM Program",
                "location": "See link",
                "team": "Product",
                "commitment": "Graduate / Early career",
                "url": job_url,
                "description": f"APM program listed on APM List. Status: {status}",
            }))

    return results


# ----------------------------
# REMOTIVE
# ----------------------------

def collect_remotive_jobs():
    url = "https://remotive.com/api/remote-jobs"
    response = safe_get(url, timeout=25)

    if isinstance(response, Exception):
        print(f"[Remotive] Error: {response}")
        return []

    jobs = response.json().get("jobs", [])
    results = []

    for job in jobs:
        results.append(normalize_job({
            "source": "Remotive",
            "company": job.get("company_name", ""),
            "title": job.get("title", ""),
            "location": job.get("candidate_required_location", "Remote"),
            "team": job.get("category", ""),
            "commitment": job.get("job_type", ""),
            "url": job.get("url", ""),
            "description": clean_html(job.get("description", "")),
        }))

    return results


# ----------------------------
# REMOTEOK
# ----------------------------

def collect_remoteok_jobs():
    url = "https://remoteok.com/api"
    response = safe_get(url, timeout=25)

    if isinstance(response, Exception):
        print(f"[RemoteOK] Error: {response}")
        return []

    try:
        data = response.json()
    except ValueError as error:
        print(f"[RemoteOK] JSON error: {error}")
        return []

    results = []

    for job in data:
        if not isinstance(job, dict) or "position" not in job:
            continue

        tags = job.get("tags", [])
        tags_text = ", ".join(tags) if isinstance(tags, list) else ""

        results.append(normalize_job({
            "source": "RemoteOK",
            "company": job.get("company", ""),
            "title": job.get("position", ""),
            "location": job.get("location", "Remote"),
            "team": tags_text,
            "commitment": "Remote",
            "url": job.get("url", ""),
            "description": clean_html(job.get("description", "")),
        }))

    return results


# ----------------------------
# THE MUSE
# ----------------------------

def collect_themuse_jobs(page_limit=THE_MUSE_PAGE_LIMIT):
    results = []

    for page in range(page_limit):
        url = f"https://www.themuse.com/api/public/jobs?page={page}"
        response = safe_get(url, timeout=25)

        if isinstance(response, Exception):
            print(f"[The Muse] Error on page {page}: {response}")
            continue

        jobs = response.json().get("results", [])

        for job in jobs:
            company = job.get("company", {}).get("name", "")

            locations = job.get("locations", [])
            location_text = ", ".join(location.get("name", "") for location in locations)

            categories = job.get("categories", [])
            category_text = ", ".join(category.get("name", "") for category in categories)

            levels = job.get("levels", [])
            level_text = ", ".join(level.get("name", "") for level in levels)

            refs = job.get("refs", {})

            results.append(normalize_job({
                "source": "The Muse",
                "company": company,
                "title": job.get("name", ""),
                "location": location_text,
                "team": category_text,
                "commitment": level_text,
                "url": refs.get("landing_page", ""),
                "description": clean_html(job.get("contents", "")),
            }))

        time.sleep(REQUEST_DELAY_SECONDS)

    return results


# ----------------------------
# COLLECT EVERYTHING
# ----------------------------

def collect_all_jobs():
    # Remove accidental duplicate slugs while preserving order.
    def dedupe(items):
        seen = set()
        result = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result

    global GREENHOUSE_COMPANIES, LEVER_COMPANIES, ASHBY_COMPANIES
    GREENHOUSE_COMPANIES = dedupe(GREENHOUSE_COMPANIES)
    LEVER_COMPANIES = dedupe(LEVER_COMPANIES)
    ASHBY_COMPANIES = dedupe(ASHBY_COMPANIES)

    all_jobs = []

    print("\n=== Collecting Greenhouse jobs ===")
    all_jobs.extend(collect_all_greenhouse_jobs())

    print("\n=== Collecting Lever jobs ===")
    all_jobs.extend(collect_all_lever_jobs())

    print("\n=== Collecting Ashby jobs ===")
    all_jobs.extend(collect_all_ashby_jobs())

    print("\n=== Collecting Workday jobs ===")
    all_jobs.extend(collect_all_workday_jobs())

    print("\n=== Collecting APM List jobs ===")
    apm_jobs = collect_apm_list_jobs()
    all_jobs.extend(apm_jobs)
    print(f"  Found {len(apm_jobs)} jobs")

    print("\n=== Collecting Remotive jobs ===")
    remotive_jobs = collect_remotive_jobs()
    all_jobs.extend(remotive_jobs)
    print(f"  Found {len(remotive_jobs)} jobs")

    print("\n=== Collecting RemoteOK jobs ===")
    remoteok_jobs = collect_remoteok_jobs()
    all_jobs.extend(remoteok_jobs)
    print(f"  Found {len(remoteok_jobs)} jobs")

    print("\n=== Collecting The Muse jobs ===")
    themuse_jobs = collect_themuse_jobs(page_limit=THE_MUSE_PAGE_LIMIT)
    all_jobs.extend(themuse_jobs)
    print(f"  Found {len(themuse_jobs)} jobs")

    print("\n=== Removing duplicates ===")
    before = len(all_jobs)
    all_jobs = remove_duplicates(all_jobs)
    after = len(all_jobs)
    print(f"  Removed {before - after} duplicates")

    return all_jobs


# ----------------------------
# MAIN
# ----------------------------

if __name__ == "__main__":
    jobs = collect_all_jobs()

    print("\n==============================")
    print(f"Total jobs collected: {len(jobs)}")
    print("==============================\n")

    df = pd.DataFrame(jobs)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"File created: {OUTPUT_FILE}")
    print()

    # Show how many jobs came from each source so empty sources are obvious.
    if not df.empty:
        print("Jobs per source:")
        for source, count in df["source"].value_counts().items():
            print(f"  {source}: {count}")
        print()

    for job in jobs[:20]:
        print("-" * 60)
        print("Source:", job.get("source"))
        print("Company:", job.get("company"))
        print("Title:", job.get("title"))
        print("Location:", job.get("location"))
        print("URL:", job.get("url"))
