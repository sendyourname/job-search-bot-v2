# Job Search Bot for Regan O'Connor

## Project Overview
Automated daily job search system that scrapes job postings, filters for relevant finance roles at startups, generates personalized cover letters using Claude AI, identifies hiring managers, and sends notifications when matches are found.

## Candidate Profile
- **Name**: Regan O'Connor
- **Email**: reganmdoconnor@gmail.com
- **Current Role**: Financial Analyst (FP&A) at Google Search & Commerce
- **Experience**: ~6 years (Google 2020-Present, Deloitte 2017-2018)
- **Credentials**: Chartered Accountant (CA), BCom - University of Sydney
- **Target**: Product/Strategic Finance at Series A-C tech startups, NYC, $150k+
- **Resume**: `data/resume.pdf`

## Architecture
```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Job Sources    │────▶│  Railway Server  │────▶│  Notifications  │
│  - LinkedIn     │     │  (Python)        │     │  - Pushover     │
│  - Wellfound    │     │                  │     │                 │
│  - Adzuna API   │     │  Daily Cron      │     │  Google Drive   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  Claude API      │
                        │  - Job matching  │
                        │  - Cover letters │
                        │  - HM research   │
                        └──────────────────┘
```

## Project Structure
```
job-search-bot/
├── src/
│   ├── main.py                 # Entry point, orchestrator
│   ├── config.py               # Configuration & search criteria
│   ├── scrapers/
│   │   ├── base.py             # Base scraper class
│   │   ├── linkedin.py         # LinkedIn job scraper (Playwright)
│   │   ├── wellfound.py        # Wellfound/AngelList scraper
│   │   └── adzuna.py           # Adzuna API client
│   ├── processors/
│   │   ├── matcher.py          # Claude-powered job matching
│   │   ├── cover_letter.py     # Cover letter generator
│   │   └── hiring_manager.py   # Hiring manager finder
│   ├── services/
│   │   ├── claude_client.py    # Anthropic API wrapper
│   │   ├── google_drive.py     # Google Drive upload
│   │   └── notifier.py         # Pushover notifications
│   └── database/
│       └── models.py           # SQLite models (job tracking)
├── data/
│   └── resume.pdf              # Regan's resume
├── templates/
│   └── cover_letter.md         # Cover letter template
├── requirements.txt
├── .env.example                # Environment variables template
├── railway.toml                # Railway deployment config
└── CLAUDE.md                   # This file
```

## Key Files
- `src/config.py` - Search criteria, candidate profile, settings
- `src/main.py` - Main orchestrator that runs the daily job search
- `src/processors/matcher.py` - Claude-powered job scoring (1-10)
- `src/processors/cover_letter.py` - Personalized cover letter generation
- `src/services/notifier.py` - Pushover push notifications

## Job Search Criteria
- **Titles**: Financial Analyst, Strategic Finance, Product Finance, FP&A, Head of Finance
- **Exclude**: GTM Finance, Sales Finance, Accounting, Tax, Payroll
- **Location**: NYC or Remote
- **Salary**: $150k+ minimum
- **Company Stage**: Seed through Series C
- **Industries**: Tech, Fintech, SaaS, AI/ML

## Required API Keys (in .env)
1. `ANTHROPIC_API_KEY` - Claude API for AI features
2. `GOOGLE_CREDENTIALS_PATH` + `GOOGLE_DRIVE_FOLDER_ID` - Google Drive
3. `PUSHOVER_USER_KEY` + `PUSHOVER_API_TOKEN` - Push notifications
4. `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` - Job aggregator API

## Running Locally
```bash
cd job-search-bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env  # Then fill in API keys
python -m src.main
```

## Deployment (Railway)
1. Push to GitHub
2. Connect repo to Railway
3. Set environment variables in Railway dashboard
4. Configure cron: `0 13 * * *` (8 AM EST daily)

## Current Status
- [x] Project structure created
- [x] Configuration and settings
- [x] Job scrapers (LinkedIn, Wellfound, Adzuna)
- [x] Claude client and job matcher
- [x] Cover letter generator
- [x] Hiring manager finder
- [x] Google Drive integration
- [x] Pushover notifications
- [x] Database for tracking seen jobs
- [x] Main orchestrator
- [x] Railway deployment config
- [x] Setup documentation

## Cost Estimate (Monthly)
- Railway: ~$5
- Claude API: ~$10-20
- Google Drive: Free
- Pushover: $5 one-time
- **Total: ~$15-25/month**
