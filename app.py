from flask import Flask, jsonify, request
from flask_cors import CORS
import requests, os, json, time
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
CACHE_FILE = "/tmp/jobs_cache.json"
CACHE_HOURS = 6

TARGET_TITLES = ["head of marketing","marketing director","director of marketing","director of brand","brand director","head of brand","head of cx","cx director","director of cx","head of customer experience","director customer experience","head of digital","digital director","senior marketing manager","senior brand manager","senior cx manager","marketing manager","brand manager","cx manager","vp marketing","vp customer experience","chief marketing","cmo"]
EXPLICIT_SKILLS = ["brand strategy","integrated campaigns","atl","btl","digital marketing","performance marketing","media planning","go-to-market","product launches","p&l management","digital channels","digital transformation","cx strategy","customer experience","nps","customer journey","omnichannel","digital adoption","fintech","digital payments","agency management","stakeholder management","strategic partnerships","influencer marketing","content marketing","social media","mena","apac","leadership","customer acquisition","customer retention","growth marketing","ecommerce","crm"]
GCC_LOCS = ["uae","dubai","abu dhabi","sharjah","saudi arabia","ksa","riyadh","jeddah","qatar","doha","kuwait","bahrain","manama","oman","muscat","gcc","gulf","middle east"]
QUERIES = ["Head of Marketing UAE","Marketing Director Dubai","Head of CX UAE","Brand Director UAE","Senior Marketing Manager UAE","Head of Marketing Saudi Arabia","Marketing Director Qatar","CX Director GCC","Digital Marketing Director Dubai","Head of Marketing GCC"]

def score_job(title, desc, loc):
    text = (title+desc+loc).lower()
    s = min(40, sum(1 for t in TARGET_TITLES if t in title.lower())*20)
    s += min(35, sum(1 for sk in EXPLICIT_SKILLS if sk in text)*3)
    if any(l in text for l in GCC_LOCS): s += 10
    return min(99, s+8)

def is_relevant(title, loc):
    return any(t in title.lower() for t in TARGET_TITLES) and any(l in (title+loc).lower() for l in GCC_LOCS)

def get_tags(title):
    tl = title.lower()
    tags = ["Head-level"] if any(t in tl for t in ["head","director","vp","chief","cmo"]) else ["Senior Manager"] if "senior" in tl else ["Manager"]
    if any(t in tl for t in ["cx","customer experience"]): tags.append("CX")
    elif "brand" in tl: tags.append("Brand")
    return tags

def fetch_jobs():
    if not RAPIDAPI_KEY: return []
    jobs = []
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}
    for query in QUERIES[:5]:
        try:
            r = requests.get("https://jsearch.p.rapidapi.com/search", headers=headers, params={"query":query,"page":"1","num_pages":"1","date_posted":"month"}, timeout=15)
            if r.status_code != 200: continue
            for job in r.json().get("data",[]):
                title = job.get("job_title","") or ""
                company = job.get("employer_name","") or ""
                loc = f"{job.get('job_city','')}, {job.get('job_country','')}".strip(", ")
                desc = (job.get("job_description","") or "")[:300]
                url = job.get("job_apply_link","") or ""
                if not title or not is_relevant(title, loc): continue
                sc = score_job(title, desc, loc)
                if sc < 40: continue
                jobs.append({"title":title,"company":company,"location":loc,"description":desc,"applyUrl":url,"source":"LinkedIn","score":sc,"posted":(job.get("job_posted_at_datetime_utc","") or "")[:10],"tags":get_tags(title),"type":"Live listing"})
            time.sleep(1)
        except Exception as e:
            print(f"Error: {e}")
    return jobs

def dedup(jobs):
    seen, out = set(), []
    for j in jobs:
        k = (j.get("title","").lower()[:25], j.get("company","").lower()[:15])
        if k not in seen: seen.add(k); out.append(j)
    return out

def load_cache():
    try:
        with open(CACHE_FILE) as f: data = json.load(f)
        if datetime.now() - datetime.fromisoformat(data["cached_at"]) < timedelta(hours=CACHE_HOURS):
            return data["jobs"]
    except: pass
    return None

def save_cache(jobs):
    try:
        with open(CACHE_FILE,"w") as f: json.dump({"cached_at":datetime.now().isoformat(),"jobs":jobs},f)
    except: pass

@app.route("/")
def index(): return jsonify({"status":"Hassaan Job API running","version":"2.0"})

@app.route("/health")
def health(): return jsonify({"status":"ok","time":datetime.now().isoformat(),"rapidapi_configured":bool(RAPIDAPI_KEY)})

@app.route("/jobs")
def get_jobs():
    force = request.args.get("refresh") == "true"
    if not force:
        cached = load_cache()
        if cached: return jsonify({"jobs":cached,"source":"cache","count":len(cached)})
    print("Fetching live jobs...")
    try:
        jobs = dedup(fetch_jobs())
        jobs.sort(key=lambda x: x.get("score",0), reverse=True)
        jobs = jobs[:100]
        save_cache(jobs)
        return jsonify({"jobs":jobs,"source":"live","count":len(jobs),"fetched_at":datetime.now().isoformat()})
    except Exception as e:
        print(f"Fetch error: {e}")
        return jsonify({"jobs":[],"source":"error","error":str(e),"count":0}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=False)
