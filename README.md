# Hassaan Zafar — Job API Backend

Fetches live jobs from LinkedIn, Indeed, GulfTalent, Bayt, Naukrigulf.
Scores each against Hassaan's profile and serves to the dashboard.

## Deploy to Render (free, 10 minutes)

### Step 1 — GitHub
1. Go to github.com → New repository → name it `hassaan-job-api`
2. Upload all 4 files: app.py, requirements.txt, render.yaml, README.md
3. Click "Commit changes"

### Step 2 — Render
1. Go to render.com → New → Web Service
2. Connect your GitHub repo `hassaan-job-api`
3. Render auto-detects Python — click Deploy
4. Wait ~3 minutes for first deploy

### Step 3 — Add your RapidAPI key
1. In Render dashboard → your service → Environment
2. Add variable: RAPIDAPI_KEY = your key from rapidapi.com
3. Click Save — service auto-restarts

### Step 4 — Get your API URL
Your backend will be live at:
`https://hassaan-job-api.onrender.com`

Test it: open `https://hassaan-job-api.onrender.com/health` in your browser.

### Step 5 — Connect to dashboard
In the dashboard HTML file, find this line:
`const BACKEND_URL = '';`
Replace with:
`const BACKEND_URL = 'https://hassaan-job-api.onrender.com';`

## API Endpoints

GET /health          — Check if API is running
GET /jobs            — Get all scored jobs (cached 6 hours)
GET /jobs?refresh=true — Force fresh fetch from all sources

## RapidAPI Setup (LinkedIn data)

1. Go to rapidapi.com → sign up free
2. Search "JSearch" by letscrape
3. Subscribe to Basic plan (free — 200 requests/month)
4. Copy your API key from "Apps" → default app → API Key
5. Add to Render environment as RAPIDAPI_KEY
