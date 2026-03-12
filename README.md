# Job Search Bot for Regan O'Connor

Automated daily job search system that finds finance roles at startups, generates personalized cover letters, and sends push notifications.

## Features

- **Daily job scraping** from LinkedIn, Wellfound (AngelList), and Adzuna
- **AI-powered matching** using Claude to score job fit (1-10)
- **Auto-generated cover letters** personalized to each role
- **Hiring manager research** with LinkedIn search links
- **Google Drive storage** - organized folders per company
- **Push notifications** via Pushover when matches are found

## Quick Start

### 1. Clone and Setup

```bash
cd ~/Desktop/job-search-bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your API keys (see Setup Guide below).

### 3. Run Locally

```bash
python -m src.main
```

## Setup Guide

### Required: Anthropic Claude API (~$10-20/month)

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up / Log in
3. Go to API Keys → Create Key
4. Copy to `.env` as `ANTHROPIC_API_KEY`

### Required: Google Drive

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project (e.g., "Job Search Bot")
3. Enable the **Google Drive API**:
   - APIs & Services → Library → Search "Drive" → Enable
4. Create a Service Account:
   - APIs & Services → Credentials → Create Credentials → Service Account
   - Name: "job-search-bot"
   - Grant "Editor" role
5. Create key for service account:
   - Click the service account → Keys → Add Key → JSON
   - Download and save as `credentials.json` in project folder
6. Create a Google Drive folder for outputs
7. **Share the folder** with the service account email (ends in `@...iam.gserviceaccount.com`)
8. Copy the folder ID from the URL: `drive.google.com/drive/folders/FOLDER_ID_HERE`
9. Add to `.env`:
   ```
   GOOGLE_CREDENTIALS_PATH=./credentials.json
   GOOGLE_DRIVE_FOLDER_ID=your-folder-id
   ```

### Required: Pushover Notifications ($5 one-time)

1. Download Pushover app on your phone ([iOS](https://apps.apple.com/app/pushover-notifications/id506088175) / [Android](https://play.google.com/store/apps/details?id=net.superblock.pushover))
2. Create account at [pushover.net](https://pushover.net)
3. Copy your **User Key** from the dashboard
4. Create an Application:
   - [Create New Application](https://pushover.net/apps/build)
   - Name: "Job Search Bot"
   - Copy the **API Token**
5. Add to `.env`:
   ```
   PUSHOVER_USER_KEY=your-user-key
   PUSHOVER_API_TOKEN=your-api-token
   ```

### Optional: Adzuna API (Free)

1. Sign up at [developer.adzuna.com](https://developer.adzuna.com)
2. Create an application
3. Add to `.env`:
   ```
   ADZUNA_APP_ID=your-app-id
   ADZUNA_APP_KEY=your-app-key
   ```

## Deploy to Railway

### 1. Push to GitHub

```bash
cd ~/Desktop/job-search-bot
git init
git add .
git commit -m "Initial commit"
gh repo create job-search-bot --private --push
```

### 2. Deploy on Railway

1. Go to [railway.app](https://railway.app) and sign in with GitHub
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your `job-search-bot` repository
4. Railway will auto-detect the config

### 3. Set Environment Variables

In Railway dashboard → Variables, add all your `.env` values:

- `ANTHROPIC_API_KEY`
- `GOOGLE_DRIVE_FOLDER_ID`
- `PUSHOVER_USER_KEY`
- `PUSHOVER_API_TOKEN`
- `ADZUNA_APP_ID` (optional)
- `ADZUNA_APP_KEY` (optional)

For Google credentials, you'll need to:
1. Copy the contents of `credentials.json`
2. Create a variable `GOOGLE_CREDENTIALS_JSON` with the JSON content
3. Modify the code to read from environment variable (or use Railway's secret files feature)

### 4. Configure Cron Schedule

The `railway.toml` is already configured to run daily at 8 AM EST.

To change the schedule, edit `railway.toml`:
```toml
[deploy.cron]
schedule = "0 13 * * *"  # 13:00 UTC = 8 AM EST
```

## Cost Estimate

| Service | Cost |
|---------|------|
| Railway | ~$5/month |
| Claude API | ~$10-20/month |
| Google Drive | Free |
| Pushover | $5 one-time |
| **Total** | **~$15-25/month** |

## Customization

### Modify Search Criteria

Edit `src/config.py`:

```python
SEARCH_CRITERIA = {
    "titles": [
        "Financial Analyst",
        "Strategic Finance",
        # Add more titles...
    ],
    "exclude_keywords": [
        "GTM Finance",
        "Sales Finance",
        # Add keywords to exclude...
    ],
    "min_salary": 150000,
    # ...
}
```

### Update Candidate Profile

Edit `src/config.py`:

```python
CANDIDATE_PROFILE = {
    "name": "Regan O'Connor",
    "current_role": "Financial Analyst (FP&A)",
    # Update as needed...
}
```

## Troubleshooting

### LinkedIn scraping fails
- LinkedIn has anti-scraping measures
- Try running with `headless=False` to debug
- Consider using LinkedIn's official API if available

### Google Drive upload fails
- Verify the service account email has access to the folder
- Check that `credentials.json` path is correct
- Ensure Drive API is enabled in Google Cloud

### Notifications not working
- Verify Pushover app is installed and logged in
- Test with: `curl -s -F "token=YOUR_TOKEN" -F "user=YOUR_KEY" -F "message=test" https://api.pushover.net/1/messages.json`

## Project Structure

```
job-search-bot/
├── src/
│   ├── main.py              # Main orchestrator
│   ├── config.py            # Configuration
│   ├── scrapers/            # Job source scrapers
│   ├── processors/          # AI processing
│   ├── services/            # External services
│   └── database/            # Job tracking
├── data/
│   └── resume.pdf           # Regan's resume
├── requirements.txt
├── .env.example
└── railway.toml
```

## License

Private - for personal use only.
# Job Search Bot
