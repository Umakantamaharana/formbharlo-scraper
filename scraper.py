import os
import time
import json
import re
from datetime import datetime
import urllib.parse
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from google import genai

# Load environment variables
load_dotenv()

# Configuration
JSON_PATH = "latest_jobs.json"
ARCHIVE_DIR = "archives"
BASE_URL = "https://www.freejobalert.com/"
MAX_ACTIVE_JOBS = 500
CAREER_PORTAL_BASE_URL = os.getenv("CAREER_PORTAL_URL", "https://formbharlo.in")

def normalize_url(url):
    """Ensure external URLs have proper http/https protocol prefix."""
    if not url:
        return ""
    trimmed = str(url).strip()
    if not trimmed:
        return ""
    if re.match(r"^https?://", trimmed, re.IGNORECASE):
        return trimmed
    return f"https://{trimmed}"

def setup_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"WebDriverManager fallback: {e}. Trying default system chromedriver.")
        driver = webdriver.Chrome(options=options)
        
    return driver

def fetch_job_links(driver=None):
    """Fetch recent job article links from FreeJobAlert."""
    print(f"Fetching job links from {BASE_URL}...")
    
    # Try lightweight requests first
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(BASE_URL, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            links = [
                a["href"] for a in soup.find_all("a", href=True)
                if a["href"].startswith("https://www.freejobalert.com/articles")
            ]
            if links:
                return list(set(links))
    except Exception as req_err:
        print(f"Direct request failed ({req_err}), attempting Selenium...")

    # Selenium Fallback
    if driver:
        driver.get(BASE_URL)
        time.sleep(4)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        links = [
            a["href"] for a in soup.find_all("a", href=True)
            if a["href"].startswith("https://www.freejobalert.com/articles")
        ]
        return list(set(links))
    
    return []

def load_jobs():
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def archive_old_jobs(all_jobs):
    """Archive older jobs when count exceeds MAX_ACTIVE_JOBS to prevent file bloat."""
    if len(all_jobs) <= MAX_ACTIVE_JOBS:
        return all_jobs

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    current_month = datetime.now().strftime("%Y_%m")
    archive_file = os.path.join(ARCHIVE_DIR, f"jobs_archive_{current_month}.json")

    # Load existing archive if present
    existing_archive = []
    if os.path.exists(archive_file):
        try:
            with open(archive_file, "r", encoding="utf-8") as f:
                existing_archive = json.load(f)
        except Exception:
            existing_archive = []

    # Sort all jobs by ID descending (newest first)
    all_jobs.sort(key=lambda x: int(x.get("id", 0)), reverse=True)
    
    active_jobs = all_jobs[:MAX_ACTIVE_JOBS]
    overflow_jobs = all_jobs[MAX_ACTIVE_JOBS:]

    # Merge overflow into archive
    archived_ids = {str(j.get("id")) for j in existing_archive}
    for item in overflow_jobs:
        if str(item.get("id")) not in archived_ids:
            existing_archive.append(item)

    try:
        with open(archive_file, "w", encoding="utf-8") as f:
            json.dump(existing_archive, f, indent=2)
        print(f"Archived {len(overflow_jobs)} older jobs into {archive_file}")
    except Exception as e:
        print(f"Warning: Failed to save archive: {e}")

    return active_jobs

def save_jobs(jobs):
    active_jobs = archive_old_jobs(jobs)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(active_jobs, f, indent=2)

def update_json(new_links):
    jobs = load_jobs()
    existing_links = {job["href"] for job in jobs}
    
    # Check archives for existing links as well
    if os.path.exists(ARCHIVE_DIR):
        for arch in os.listdir(ARCHIVE_DIR):
            if arch.endswith(".json"):
                try:
                    with open(os.path.join(ARCHIVE_DIR, arch), "r", encoding="utf-8") as f:
                        arch_jobs = json.load(f)
                        for aj in arch_jobs:
                            if "href" in aj:
                                existing_links.add(aj["href"])
                except Exception:
                    pass
    
    current_max_id = 0
    if jobs:
        try:
            current_max_id = max(int(job.get("id", 0)) for job in jobs)
        except ValueError:
            current_max_id = 0
    
    new_entries_count = 0
    for link in new_links:
        if link not in existing_links:
            current_max_id += 1
            new_job = {
                "id": str(current_max_id),
                "href": link,
                "status": "UNPUBLISHED",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "category": "General",
                "organization": "",
                "vacancies": "",
                "qualification": "",
                "deadline": "",
                "location": "All India",
                "type": "Full-time",
                "website_content": {},
                "social_posts": {
                    "x": "", "ln": "", "fb": "", "ig": "", "th": "", "wp": "", "tg": ""
                }
            }
            jobs.append(new_job)
            new_entries_count += 1
            existing_links.add(link)
            
    if new_entries_count > 0:
        save_jobs(jobs)
        print(f"Added {new_entries_count} new job entries to {JSON_PATH}.")
    else:
        print("No new job links found.")
        
    return jobs

def extract_content(html):
    soup = BeautifulSoup(html, "html.parser")
    
    for tag in soup(["script", "style", "noscript", "iframe", "footer", "aside", "nav"]):
        tag.decompose()

    main_content = soup.find("div", class_="entry-content")
    if not main_content:
        main_content = soup.find("article") or soup.find("main")

    if main_content:
        for ad in main_content.find_all(class_=re.compile(r"ad_div|advertisement|adsbygoogle", re.I)):
            ad.decompose()
        return main_content.get_text(separator="\n", strip=True)
    return ""

def generate_content_and_posts(content, client):
    if not content:
        return None
        
    prompt = """You are a senior recruitment editor and social media growth specialist for FormBharlo.
Extract rich, structured recruitment data and generate viral social media announcements from this raw notification text.

Raw Job Description:
{content}

Output MUST be a valid JSON object matching this exact structure:
{{
  "category": "One of: Government | Banking | Engineering | Healthcare | Defence | Teaching | State Exams | General",
  "organization": "Exact recruiting authority name (e.g., RRB, UPSC, SSC, AIIMS, SBI, BSNL, WBHRB)",
  "vacancies": "Total number of vacancies (e.g., '22,000' or '120' or 'Multiple')",
  "qualification": "Required education (e.g., '10th/12th Pass', 'Graduate', 'B.Tech', 'GNM / B.Sc Nursing')",
  "deadline": "Application deadline date in YYYY-MM-DD or 'Check Notification'",
  "location": "Job posting location / State or 'All India'",
  "salary": "Pay scale / stipend if mentioned, or 'As per Govt Norms'",
  "website_content": {{
    "title": "Clear, informative job title with year (e.g., 'WBHRB Staff Nurse Grade II Scorecard 2026')",
    "summary": "2-sentence executive summary highlighting post name, key date, and authority.",
    "markdown_content": "Detailed, cleanly formatted Markdown with ## Headings, bullet lists (*), key highlights (**bold**), eligibility, and important dates. Do NOT include official links here.",
    "actual_link": "Direct official website URL starting with https://. If not found, output empty string.",
    "action": "Short action CTA (e.g. 'Apply Online', 'Check Result', 'Download Admit Card', 'View Answer Key')"
  }},
  "social_posts": {{
    "x": "Twitter announcement (max 220 chars) with #FormBharlo hashtags and the official link.",
    "ln": "LinkedIn announcement (professional, bullet points).",
    "fb": "Facebook post with engaging tone and key dates.",
    "ig": "Instagram caption with hashtags and 'Link in bio' prompt.",
    "wp": "WhatsApp broadcast message (concise with bullet points and direct link).",
    "th": "Threads conversation post.",
    "tg": "Telegram broadcast channel post with emoji badges and direct application link."
  }}
}}
"""
    
    formatted_prompt = prompt.format(content=content[:12000])
    raw_model = (os.getenv("GEMINI_MODEL") or "gemma-4-31b-it").strip().lower()
    
    candidate_models = [raw_model]
    for fallback in ['gemma-4-31b-it', 'gemini-3.7-flash', 'gemini-3.6-flash']:
        if fallback not in candidate_models:
            candidate_models.append(fallback)
            
    for m in candidate_models:
        # 1. Try Interactions API (Google GenAI latest standard)
        if hasattr(client, 'interactions'):
            try:
                interaction = client.interactions.create(
                    model=m,
                    input=formatted_prompt
                )
                output = getattr(interaction, 'output_text', getattr(interaction, 'text', None))
                if output:
                    return str(output)
            except Exception as interaction_err:
                print(f"Interactions API '{m}' notice: {interaction_err}")

        # 2. Fallback to Models API
        try:
            response = client.models.generate_content(
                model=m,
                contents=formatted_prompt,
            )
            if response and getattr(response, 'text', None):
                return response.text
        except Exception as model_err:
            print(f"Models API '{m}' error: {model_err}")
            continue

    return None

import html

def broadcast_to_telegram(job):
    """Automatically broadcast new job notification to Telegram channel."""
    bot_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    channel_id = (os.getenv("TELEGRAM_CHANNEL_ID") or "").strip()
    
    if not bot_token or not channel_id:
        return False
        
    # Ensure public username starts with @ if not numeric
    if not channel_id.startswith("@") and not channel_id.startswith("-100") and not channel_id.startswith("-"):
        channel_id = f"@{channel_id}"
        
    title = html.escape(job.get("website_content", {}).get("title") or "New Govt Job Notification")
    category = html.escape(job.get("category", "Government"))
    org = html.escape(job.get("organization", ""))
    vacancies = html.escape(str(job.get("vacancies", "")))
    job_id = job.get("id", "")
    career_url = f"{CAREER_PORTAL_BASE_URL}/job/{job_id}"
    direct_link = job.get("website_content", {}).get("actual_link", "")
    action = html.escape(job.get("website_content", {}).get("action", "Apply Now"))

    message_lines = [
        f"🚨 <b>NEW NOTIFICATION 2026</b>",
        f"<b>{title}</b>",
        f"",
        f"🏢 <b>Authority:</b> {org}" if org else "",
        f"📂 <b>Category:</b> #{category.replace(' ', '')}",
        f"👥 <b>Vacancies:</b> {vacancies}" if vacancies else "",
        f"",
        f"🔗 <b>Full Details:</b> <a href=\"{career_url}\">View on FormBharlo</a>",
        f"⚡ <b>Direct Portal:</b> <a href=\"{direct_link}\">{action}</a>" if direct_link else "",
        f"",
        f"📢 <i>Share with friends &amp; job aspirants!</i>"
    ]
    message_text = "\n".join([line for line in message_lines if line])
    
    try:
        api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": channel_id,
            "text": message_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        res = requests.post(api_url, json=payload, timeout=8)
        if res.status_code == 200:
            print(f"Broadcasted job {job_id} to Telegram successfully.")
            return True
        else:
            print(f"Telegram API warning: {res.text}")
    except Exception as e:
        print(f"Failed to post to Telegram: {e}")
    return False

def trigger_vercel_revalidation():
    """Optional: Trigger Vercel Deploy Hook to rebuild static cache."""
    webhook_url = os.getenv("VERCEL_DEPLOY_HOOK_URL")
    if not webhook_url:
        return
    try:
        res = requests.post(webhook_url, timeout=10)
        print(f"Triggered Vercel webhook. Status: {res.status_code}")
    except Exception as e:
        print(f"Vercel webhook error: {e}")

def update_job_status(job_id, new_status):
    jobs = load_jobs()
    updated = False
    for job in jobs:
        if str(job.get("id")) == str(job_id):
            job["status"] = new_status
            updated = True
            break
    if updated:
        save_jobs(jobs)
        return True
    return False

def update_job_link(job_id, new_link):
    jobs = load_jobs()
    updated = False
    for job in jobs:
        if str(job.get("id")) == str(job_id):
            if "website_content" not in job:
                job["website_content"] = {}
            job["website_content"]["actual_link"] = normalize_url(new_link)
            updated = True
            break
    if updated:
        save_jobs(jobs)
        return True
    return False

def get_jobs_json():
    return load_jobs()

def process_jobs(progress_callback=None):
    driver = setup_driver()
    RATE_LIMIT_DELAY = 2.0
    MAX_RETRIES = 3
    
    try:
        if progress_callback: progress_callback("Fetching latest job links...")
        links = fetch_job_links(driver)
        jobs = update_json(links)
        # Sort UNPUBLISHED jobs by newest ID first and limit batch to avoid quota exhaustion
        BATCH_SIZE = int(os.getenv("SCRAPE_BATCH_SIZE", "25"))
        unpublished_jobs = [job for job in jobs if job.get("status") == "UNPUBLISHED"]
        unpublished_jobs.sort(key=lambda x: int(x.get("id", 0)), reverse=True)
        jobs_to_process = unpublished_jobs[:BATCH_SIZE]
        total_jobs = len(jobs_to_process)
        
        if total_jobs == 0:
            print("No new jobs to process.")
            if progress_callback: progress_callback("No new jobs to process.")
            return
            
        print(f"Found {len(unpublished_jobs)} pending jobs. Processing newest {total_jobs} in this batch.")

        api_key = (os.getenv("GOOGLE_API_KEY") or "").strip()
        if not api_key:
            print("GOOGLE_API_KEY not found. Skipping AI content generation.")
            client = None
        else:
            client = genai.Client(api_key=api_key)

        processed_any = False
        for i, job in enumerate(jobs_to_process):
            url = job["href"]
            job_id = job["id"]
            msg = f"Processing [{i+1}/{total_jobs}] ID #{job_id}: {url}"
            print(msg)
            if progress_callback: progress_callback(msg)
            
            time.sleep(RATE_LIMIT_DELAY)
            
            try:
                # Extract article body
                content = None
                try:
                    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    if res.status_code == 200:
                        content = extract_content(res.text)
                except Exception:
                    pass

                if not content:
                    driver.get(url)
                    time.sleep(2.5)
                    content = extract_content(driver.page_source)
                
                if content:
                    generated_data = None
                    if client:
                        for attempt in range(MAX_RETRIES):
                            try:
                                json_str = generate_content_and_posts(content, client)
                                if json_str:
                                    clean_json = json_str.strip()
                                    if clean_json.startswith("```json"):
                                        clean_json = clean_json[7:]
                                    elif clean_json.startswith("```"):
                                        clean_json = clean_json[3:]
                                    if clean_json.endswith("```"):
                                        clean_json = clean_json[:-3]
                                    clean_json = clean_json.strip()
                                    
                                    generated_data = json.loads(clean_json)
                                    break
                                else:
                                    print(f"Attempt {attempt+1}: No response from AI model.")
                            except json.JSONDecodeError as e:
                                print(f"Attempt {attempt+1}: JSON Parse Error: {e}")
                            except Exception as e:
                                print(f"Attempt {attempt+1}: API Error: {e}")
                            time.sleep(2)
                    
                    if generated_data:
                        print(f"Successfully generated structured content for {url}")
                        for mutable_job in jobs:
                            if mutable_job.get("id") == job_id:
                                # Populate structured root fields
                                mutable_job["category"] = generated_data.get("category", "Government")
                                mutable_job["organization"] = generated_data.get("organization", "")
                                mutable_job["vacancies"] = generated_data.get("vacancies", "")
                                mutable_job["qualification"] = generated_data.get("qualification", "")
                                mutable_job["deadline"] = generated_data.get("deadline", "")
                                mutable_job["location"] = generated_data.get("location", "All India")
                                mutable_job["salary"] = generated_data.get("salary", "")
                                
                                # Website content
                                web_content = generated_data.get("website_content", {})
                                web_content["actual_link"] = normalize_url(web_content.get("actual_link", ""))
                                mutable_job["website_content"] = web_content
                                mutable_job["social_posts"] = generated_data.get("social_posts", {})
                                mutable_job["status"] = "GENERATED"
                                
                                # Broadcast to Telegram if configured
                                broadcast_to_telegram(mutable_job)
                                break
                        
                        save_jobs(jobs)
                        processed_any = True
                    else:
                        print(f"Failed to generate structured data for {url}")
                else:
                    print(f"No content extracted from {url}")
            except Exception as e:
                print(f"Error processing {url}: {e}")
        
        if processed_any:
            trigger_vercel_revalidation()
            
        if progress_callback: progress_callback("Processing complete.")
                
    finally:
        driver.quit()

if __name__ == "__main__":
    process_jobs()
