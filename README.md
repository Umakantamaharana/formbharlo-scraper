# Job Scraper & AI Engine Backend

> Automated recruitment scraping engine, Google Gemini AI structured data extractor, Flask management console, and Telegram broadcast automation for **Career135**.

---

## 🛠️ Technology Stack

- **Language**: Python 3.10+
- **AI / LLM Framework**: [Google GenAI SDK](https://github.com/google-gemini/generative-ai-python) (`gemini-2.5-flash` / `gemini-2.0-flash`)
- **Scraping & Parsing**: [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/), [Requests](https://requests.readthedocs.io/), [Selenium WebDriver](https://www.selenium.dev/)
- **Web Dashboard**: [Flask](https://flask.palletsprojects.com/)
- **Automation & Scheduling**: GitHub Actions (3x Daily Cron)

---

## 📂 Directory Layout

```
job-scrapper-backend/
├── scraper.py                 # Core scraping engine, Gemini AI prompt, and Telegram broadcaster
├── app.py                     # Flask web server & management dashboard API
├── index.html                 # Web dashboard UI for manual job management
├── latest_jobs.json           # Active live recruitment dataset (capped at 500 records)
├── archives/                  # Monthly historical archives (e.g. jobs_archive_2026_02.json)
├── public/job_images/         # Uploaded / cached recruitment announcement banners
├── .github/workflows/
│   └── scrape.yml             # GitHub Actions automated 3x daily scraping & commit workflow
├── requirements.txt           # Python dependency specifications
├── .env.example               # Environment variables template
└── PLAN.md                    # Engineering architecture & roadmap
```

---

## ⚙️ Environment Variables

Create a `.env` file in the root of `job-scrapper-backend`:

```env
# Google Gemini API Key (Required for AI content extraction)
GOOGLE_API_KEY=your_google_gemini_api_key_here

# Gemini Model Selection (Defaults to gemini-2.5-flash)
GEMINI_MODEL=gemini-2.5-flash

# Base URL for generated Telegram application links
CAREER_PORTAL_URL=https://career135.com

# Automated Telegram Broadcast (Optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHANNEL_ID=@your_channel_or_chat_id

# Vercel Deploy Hook URL to trigger instant site rebuilds on new jobs (Optional)
VERCEL_DEPLOY_HOOK_URL=https://api.vercel.com/v1/integrations/deploy/...
```

---

## 🚀 Installation & Local Execution

### 1. Set Up Environment
```bash
# Create and activate Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

### 2. Running the Scraper
```bash
# Runs the full scraping and AI generation pipeline
python3 scraper.py
```

### 3. Running the Flask Management Dashboard
```bash
# Starts the local management interface at http://localhost:5000
python3 app.py
```

---

## 🔄 Core Data Architecture

### 1. Structured AI Extraction Schema
When `scraper.py` parses a recruitment article, it feeds cleaned HTML to Google Gemini, producing rich, structured metadata:

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique sequential identifier |
| `status` | `string` | `GENERATED`, `PUBLISHED`, or `UNPUBLISHED` |
| `category` | `string` | `Government`, `Banking`, `Engineering`, `Healthcare`, `Defence`, `Teaching`, `State Exams` |
| `organization` | `string` | Normalized recruiting body (e.g. *RRB, SSC, UPSC, AIIMS, SBI*) |
| `vacancies` | `string` | Number of openings (e.g. *22,000* or *Multiple*) |
| `qualification` | `string` | Educational eligibility (e.g. *10th/12th Pass, Graduate, B.Tech*) |
| `deadline` | `string` | Closing date in `YYYY-MM-DD` |
| `location` | `string` | State or `All India` |
| `website_content` | `object` | Formatted Markdown article, summary, action CTA, and normalized `actual_link` |
| `social_posts` | `object` | Ready-to-publish plain-text posts for X, LinkedIn, Facebook, Instagram, WhatsApp, Threads, Telegram |

### 2. Active Windowing & Archival System
To prevent `latest_jobs.json` from bloating over time:
- `latest_jobs.json` maintains the **latest 500 active jobs** (< 500 KB).
- Older or overflow records are automatically moved to monthly archive files inside the `archives/` directory (`archives/jobs_archive_YYYY_MM.json`).

### 3. Automated Telegram Broadcast Bot
Whenever a new recruitment notice is processed:
- `broadcast_to_telegram(job)` constructs a formatted notification with authority, vacancies, category hashtags, and direct Career135 application links.
- Automatically posts to your Telegram channel via the Telegram Bot API.

---

## ⏰ Automated GitHub Actions Workflow

The automated workflow located at `.github/workflows/scrape.yml`:
- Runs **3 times daily** (08:30 AM, 02:30 PM, 07:30 PM IST / `0 3,9,14 * * *`).
- Configures headless Chrome and executes `python scraper.py`.
- Commits updated `latest_jobs.json` and `archives/` back to the repository with `[skip ci]`.
- Triggers the `VERCEL_DEPLOY_HOOK_URL` (if configured) to regenerate static frontend pages automatically.
