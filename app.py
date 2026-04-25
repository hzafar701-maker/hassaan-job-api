"""
Hassaan Zafar — UAE Job Command Centre Backend
Fetches live jobs from LinkedIn (RapidAPI), Indeed, GulfTalent, Bayt, Naukrigulf
Scores each against Hassaan's profile and serves to the dashboard
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
import json
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)  # Allow dashboard to call this API from any URL

# ── CONFIG ──────────────────────────────────────────────────────────────
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")  # Set in Render environment vars
CACHE_FILE = "/tmp/jobs_cache.json"
CACHE_HOURS = 6  # Refresh every 6 hours

# ── HASSAAN'S PROFILE FOR SCORING ───────────────────────────────────────
EXPLICIT_SKILLS = [
    "brand strategy", "integrated campaigns", "atl", "btl", "digital marketing",
    "performance marketing", "media planning", "go-to-market", "gtm", "product launches",
    "p&l management", "digital channels", "digital transformation", "cx strategy",
    "customer experience", "nps", "customer journey", "omnichannel", "digital adoption",
    "fintech", "digital payments", "google pay", "agency management", "stakeholder management",
    "strategic partnerships", "sponsorships", "influencer marketing", "content marketing",
    "social media", "mena", "apac", "leadership", "customer acquisition", "customer retention",
    "brand equity", "market research", "consumer insights", "loyalty programmes",
    "marketing analytics", "growth marketing", "ecommerce", "crm", "b2c marketing"
]

LATENT_SKILLS = [
    "influencer marketing", "content marketing", "social media marketing", "crm",
    "loyalty programmes", "growth marketing", "ecommerce", "b2c marketing",
    "marketing analytics", "shopper marketing", "media strategy", "brand communications"
]

GCC_COUNTRIES = ["UAE", "Dubai", "Abu Dhabi", "Saudi Arabia", "KSA", "Riyadh", "Jeddah",
                 "Qatar", "Doha", "Kuwait", "Bahrain", "Manama", "Oman", "Muscat"]

TARGET_TITLES = [
    "head of marketing", "marketing director", "director of marketing", "director of brand",
    "brand director", "head of brand", "head of cx", "cx director", "director of cx",
    "head of customer experience", "director customer experience", "head of digital",
    "digital director", "head of channels", "senior marketing manager", "senior brand manager",
    "senior cx manager", "marketing manager", "brand manager", "cx manager",
    "vp marketing", "vp customer experience", "chief marketing", "cmo"
]

def score_job(title, description, location):
    """Score a job against Hassaan's profile. Returns 0-100."""
    text = (title + " " + description + " " + location).lower()
    score = 0

    # Title relevance (0-40 pts)
    title_lower = title.lower()
    title_matches = sum(1 for t in TARGET_TITLES if t in title_lower)
    score += min(40, title_matches * 20)

    # Explicit skills match (0-35 pts)
    explicit_matches = sum(1 for s in EXPLICIT_SKILLS if s in text)
    score += min(35, explicit_matches * 3)

    # Latent skills (0-15 pts)
    latent_matches = sum(1 for s in LATENT_SKILLS if s in text)
    score += min(15, latent_matches * 3)

    # GCC location bonus (0-10 pts)
    if any(c.lower() in text for c in GCC_COUNTRIES):
        score += 10

    return min(99, max(0, score))

def is_relevant(title, location):
    """Quick filter — is this job even worth scoring?"""
    title_lower = title.lower()
    location_lower = location.lower()
    # Must have at least one target keyword
    has_title = any(t in title_lower for t in TARGET_TITLES)
    # Must be GCC
    is_gcc = any(c.lower() in location_lower for c in GCC_COUNTRIES)
    return has_title and is_gcc

# ── JOB SOURCES ─────────────────────────────────────────────────────────

def fetch_linkedin_rapidapi():
    """Fetch LinkedIn jobs via JSearch API on RapidAPI (legal, official)"""
    if not RAPIDAPI_KEY:
        print("No RapidAPI key set — skipping LinkedIn")
        return []

    jobs = []
    queries = [
        "Head of Marketing UAE", "Marketing Director Dubai",
        "Head of CX UAE", "CX Director Dubai", "Brand Director UAE",
        "Senior Marketing Manager UAE", "Digital Channels Director UAE",
        "Head of Marketing Saudi Arabia", "Marketing Director Riyadh",
        "Head of Marketing Qatar", "CX Director GCC"
    ]

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }

    for query in queries[:6]:  # Limit to 6 to stay within free tier
        try:
            response = requests.get(
                "https://jsearch.p.rapidapi.com/search",
                headers=headers,
                params={"query": query, "page": "1", "num_pages": "1", "date_posted": "week"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                for job in data.get("data", []):
                    title = job.get("job_title", "")
                    company = job.get("employer_name", "")
                    location = f"{job.get('job_city', '')}, {job.get('job_country', '')}"
                    description = job.get("job_description", "")[:500]
                    apply_url = job.get("job_apply_link", "")
                    posted = job.get("job_posted_at_datetime_utc", "")

                    if is_relevant(title, location):
                        match_score = score_job(title, description, location)
                        if match_score >= 50:
                            jobs.append({
                                "title": title,
                                "company": company,
                                "location": location,
                                "description": description,
                                "applyUrl": apply_url,
                                "source": "LinkedIn",
                                "score": match_score,
                                "posted": posted[:10] if posted else "",
                                "tags": get_tags(title)
                            })
            time.sleep(0.5)  # Rate limiting
        except Exception as e:
            print(f"LinkedIn API error for '{query}': {e}")

    return jobs

def fetch_indeed():
    """Scrape Indeed UAE jobs"""
    jobs = []
    searches = [
        ("head of marketing UAE", "https://ae.indeed.com/jobs?q=head+of+marketing&l=United+Arab+Emirates&fromage=14"),
        ("marketing director UAE", "https://ae.indeed.com/jobs?q=marketing+director&l=United+Arab+Emirates&fromage=14"),
        ("head of cx UAE", "https://ae.indeed.com/jobs?q=head+of+customer+experience&l=United+Arab+Emirates&fromage=14"),
        ("brand director UAE", "https://ae.indeed.com/jobs?q=brand+director&l=United+Arab+Emirates&fromage=14"),
        ("head of marketing Saudi", "https://sa.indeed.com/jobs?q=head+of+marketing&l=Saudi+Arabia&fromage=14"),
        ("marketing director Qatar", "https://qa.indeed.com/jobs?q=marketing+director&l=Qatar&fromage=14"),
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }

    for search_name, url in searches:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("div", class_="job_seen_beacon") or soup.find_all("div", {"data-testid": "slider_item"})

            for card in cards[:8]:
                try:
                    title_el = card.find("h2", class_="jobTitle") or card.find("a", {"data-testid": "job-title"})
                    title = title_el.get_text(strip=True) if title_el else ""
                    company_el = card.find("span", {"data-testid": "company-name"}) or card.find("span", class_="companyName")
                    company = company_el.get_text(strip=True) if company_el else ""
                    loc_el = card.find("div", {"data-testid": "text-location"}) or card.find("div", class_="companyLocation")
                    location = loc_el.get_text(strip=True) if loc_el else search_name.split(" ")[-1]
                    link_el = card.find("a", href=True)
                    apply_url = "https://ae.indeed.com" + link_el["href"] if link_el and link_el["href"].startswith("/") else ""
                    desc_el = card.find("div", class_="job-snippet") or card.find("div", {"data-testid": "job-snippet"})
                    description = desc_el.get_text(strip=True) if desc_el else ""

                    if title and is_relevant(title, location):
                        match_score = score_job(title, description, location)
                        if match_score >= 50:
                            jobs.append({
                                "title": title, "company": company, "location": location,
                                "description": description, "applyUrl": apply_url,
                                "source": "Indeed", "score": match_score, "posted": "",
                                "tags": get_tags(title)
                            })
                except Exception:
                    continue
            time.sleep(1)
        except Exception as e:
            print(f"Indeed scrape error for {search_name}: {e}")

    return jobs

def fetch_gulfjob():
    """Scrape GulfTalent jobs"""
    jobs = []
    urls = [
        "https://www.gulftalent.com/jobs/marketing-director-jobs-in-uae",
        "https://www.gulftalent.com/jobs/marketing-director-jobs-in-saudi-arabia",
        "https://www.gulftalent.com/jobs/head-of-marketing-jobs-in-uae",
        "https://www.gulftalent.com/jobs/customer-experience-jobs-in-uae",
    ]

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for url in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("div", class_="job-listing") or soup.find_all("article", class_="job")

            for card in cards[:6]:
                try:
                    title_el = card.find("h2") or card.find("h3") or card.find("a", class_="job-title")
                    title = title_el.get_text(strip=True) if title_el else ""
                    company_el = card.find("span", class_="company") or card.find("div", class_="company-name")
                    company = company_el.get_text(strip=True) if company_el else ""
                    loc_el = card.find("span", class_="location") or card.find("div", class_="location")
                    location = loc_el.get_text(strip=True) if loc_el else "UAE"
                    link_el = card.find("a", href=True)
                    apply_url = link_el["href"] if link_el else url

                    if title and is_relevant(title, location):
                        match_score = score_job(title, "", location)
                        if match_score >= 50:
                            jobs.append({
                                "title": title, "company": company, "location": location,
                                "description": "", "applyUrl": apply_url,
                                "source": "GulfTalent", "score": match_score, "posted": "",
                                "tags": get_tags(title)
                            })
                except Exception:
                    continue
            time.sleep(1)
        except Exception as e:
            print(f"GulfTalent error: {e}")

    return jobs

def fetch_bayt():
    """Scrape Bayt.com jobs"""
    jobs = []
    urls = [
        "https://www.bayt.com/en/uae/jobs/head-of-marketing-jobs/",
        "https://www.bayt.com/en/uae/jobs/marketing-director-jobs/",
        "https://www.bayt.com/en/uae/jobs/customer-experience-manager-jobs/",
        "https://www.bayt.com/en/saudi-arabia/jobs/head-of-marketing-jobs/",
        "https://www.bayt.com/en/qatar/jobs/marketing-director-jobs/",
    ]

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for url in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("li", {"data-js-job": True}) or soup.find_all("div", class_="media-list-item")

            for card in cards[:6]:
                try:
                    title_el = card.find("h2") or card.find("b", class_="jb-title")
                    title = title_el.get_text(strip=True) if title_el else ""
                    company_el = card.find("b", class_="jb-company") or card.find("span", class_="company")
                    company = company_el.get_text(strip=True) if company_el else ""
                    loc_el = card.find("span", class_="jb-loc") or card.find("span", class_="location")
                    location = loc_el.get_text(strip=True) if loc_el else "UAE"
                    link_el = card.find("a", href=True)
                    apply_url = "https://www.bayt.com" + link_el["href"] if link_el and link_el["href"].startswith("/") else url

                    if title and is_relevant(title, location):
                        match_score = score_job(title, "", location)
                        if match_score >= 50:
                            jobs.append({
                                "title": title, "company": company, "location": location,
                                "description": "", "applyUrl": apply_url,
                                "source": "Bayt", "score": match_score, "posted": "",
                                "tags": get_tags(title)
                            })
                except Exception:
                    continue
            time.sleep(1)
        except Exception as e:
            print(f"Bayt error: {e}")

    return jobs

def fetch_naukrigulf():
    """Scrape Naukrigulf jobs"""
    jobs = []
    urls = [
        "https://www.naukrigulf.com/marketing-director-jobs-in-uae",
        "https://www.naukrigulf.com/head-of-marketing-jobs-in-uae",
        "https://www.naukrigulf.com/customer-experience-jobs-in-uae",
        "https://www.naukrigulf.com/marketing-director-jobs-in-saudi-arabia",
    ]

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for url in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("div", class_="jobTuple") or soup.find_all("article", class_="jobTupleHeader")

            for card in cards[:6]:
                try:
                    title_el = card.find("a", class_="title") or card.find("a", {"data-type": "Job"})
                    title = title_el.get_text(strip=True) if title_el else ""
                    company_el = card.find("a", class_="subTitle") or card.find("span", class_="companyName")
                    company = company_el.get_text(strip=True) if company_el else ""
                    loc_el = card.find("li", class_="location") or card.find("span", class_="location")
                    location = loc_el.get_text(strip=True) if loc_el else "UAE"
                    link_el = title_el if title_el and title_el.get("href") else card.find("a", href=True)
                    href = link_el.get("href", "") if link_el else ""
                    apply_url = href if href.startswith("http") else "https://www.naukrigulf.com" + href

                    if title and is_relevant(title, location):
                        match_score = score_job(title, "", location)
                        if match_score >= 50:
                            jobs.append({
                                "title": title, "company": company, "location": location,
                                "description": "", "applyUrl": apply_url,
                                "source": "Naukrigulf", "score": match_score, "posted": "",
                                "tags": get_tags(title)
                            })
                except Exception:
                    continue
            time.sleep(1)
        except Exception as e:
            print(f"Naukrigulf error: {e}")

    return jobs

def get_tags(title):
    """Generate tags from job title"""
    title_lower = title.lower()
    tags = []
    if any(t in title_lower for t in ["head", "director", "vp", "chief", "cmo"]):
        tags.append("Head-level")
    elif any(t in title_lower for t in ["senior manager", "senior"]):
        tags.append("Senior Manager")
    else:
        tags.append("Manager")
    if any(t in title_lower for t in ["cx", "customer experience"]):
        tags.append("CX")
    elif any(t in title_lower for t in ["brand"]):
        tags.append("Brand")
    elif any(t in title_lower for t in ["digital"]):
        tags.append("Digital")
    return tags

def deduplicate(jobs):
    """Remove duplicate jobs by title+company"""
    seen = set()
    unique = []
    for j in jobs:
        key = (j["title"].lower()[:30], j["company"].lower()[:20])
        if key not in seen:
            seen.add(key)
            unique.append(j)
    return unique

# ── CACHE ────────────────────────────────────────────────────────────────

def load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
            cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
            if datetime.now() - cached_at < timedelta(hours=CACHE_HOURS):
                print(f"Serving from cache ({len(data['jobs'])} jobs)")
                return data["jobs"]
    except Exception:
        pass
    return None

def save_cache(jobs):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({"cached_at": datetime.now().isoformat(), "jobs": jobs}, f)
    except Exception as e:
        print(f"Cache save error: {e}")

# ── ROUTES ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return jsonify({"status": "Hassaan Zafar Job API is running", "version": "1.0"})

@app.route("/jobs")
def get_jobs():
    """Main endpoint — returns all live jobs scored against Hassaan's profile"""
    force_refresh = request.args.get("refresh") == "true"

    if not force_refresh:
        cached = load_cache()
        if cached:
            return jsonify({"jobs": cached, "source": "cache", "count": len(cached)})

    print("Fetching fresh jobs from all sources...")
    all_jobs = []

    # Fetch from all sources
    print("→ LinkedIn (RapidAPI)...")
    all_jobs.extend(fetch_linkedin_rapidapi())

    print("→ Indeed...")
    all_jobs.extend(fetch_indeed())

    print("→ GulfTalent...")
    all_jobs.extend(fetch_gulfjob())

    print("→ Bayt...")
    all_jobs.extend(fetch_bayt())

    print("→ Naukrigulf...")
    all_jobs.extend(fetch_naukrigulf())

    # Deduplicate and sort by score
    jobs = deduplicate(all_jobs)
    jobs.sort(key=lambda x: x["score"], reverse=True)

    # Keep top 100
    jobs = jobs[:100]

    save_cache(jobs)
    print(f"Done. {len(jobs)} jobs fetched and scored.")

    return jsonify({"jobs": jobs, "source": "live", "count": len(jobs), "fetched_at": datetime.now().isoformat()})

@app.route("/jobs/refresh")
def refresh_jobs():
    """Force refresh all job sources"""
    return get_jobs.__wrapped__() if hasattr(get_jobs, "__wrapped__") else jsonify({"error": "use /jobs?refresh=true"})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat(), "rapidapi_configured": bool(RAPIDAPI_KEY)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
