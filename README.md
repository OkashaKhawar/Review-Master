# Review Master

WhatsApp-based review collection and management system for businesses. Automate customer outreach, collect feedback via WhatsApp, analyze sentiment with AI, and redirect positive reviewers to Google.

---

## Features

- **User Authentication** — Sign up / login with per-user data isolation
- **Business Analytics** — Auto-scrape Google rating, review count, and location from your Maps link
- **Customer Management** — Add customers manually or bulk-import from Excel/CSV
- **WhatsApp Integration** — Send personalized review requests via WhatsApp Web (Selenium)
- **AI Sentiment Analysis** — Classify customer replies as Positive / Neutral / Negative using LLM (OpenRouter)
- **Google Review Redirect** — Automatically send a Google Review link to positive responders
- **Modern Dashboard** — Glassmorphism UI with stats, quick actions, and real-time status
- **Session Persistence** — Scan QR code once; Chrome profile is saved for future sessions

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and set:

```env
GOOGLE_REVIEW_LINK=https://search.google.com/local/writereview?placeid=YOUR_ID
OPENROUTER_API_KEY=your_key  # Optional, for LLM-based sentiment analysis
```

### 3. Start the Web Dashboard

```bash
python main.py
```

Open **http://127.0.0.1:8000** in your browser.

---

## Workflow

### Step 1 — Create an Account

1. Navigate to `/signup`
2. Enter your email, name, password, business name, and Google Maps link
3. The system auto-scrapes your business rating, total reviews, and location

### Step 2 — Import Customer Data

1. After signup, you're directed to the **Import Data** page (`/setup`)
2. Upload an Excel (`.xlsx`, `.xls`) or CSV file with customer data
3. The system auto-detects **Name**, **Phone**, and **Product** columns
4. Customers are saved to the database under your account

### Step 3 — Connect WhatsApp

1. Go to **Connect WhatsApp** from the dashboard
2. Click **Launch WhatsApp** — a Chrome browser opens with WhatsApp Web
3. Scan the QR code with your phone
4. Wait for chats to load, then click **I'm Connected**
5. Your session is saved in `whatsapp_profile/` for future use

### Step 4 — Send Review Requests

**From the Dashboard (one-by-one):**
- Use **Quick Actions** to send review requests to pending customers
- Or select a customer and click **Request Review** / **Send Test**

**Bulk Campaign (automated):**

```bash
python run_campaign.py
```

This processes all pending customers:
1. Sends a personalized review request via WhatsApp
2. Waits for the customer's reply (up to 5 minutes)
3. Analyzes sentiment using AI
4. If positive → sends Google Review link
5. If neutral/negative → sends a thank-you message
6. Updates customer status in the database

### Step 5 — Monitor Results

- View stats on the dashboard: total customers, pending, completed, positive reviews, conversion rate
- Business analytics section shows your Google rating and total reviews
- Each customer row shows their current status and sentiment

---

## Directory Structure

```
ReviewHarvest/
├── main.py                              # Web server entry point
├── run_campaign.py                      # Bulk WhatsApp campaign runner
├── requirements.txt                     # Python dependencies
├── .env                                 # Environment variables (create from .env.example)
├── src/
│   ├── web/
│   │   └── app.py                       # FastAPI app, routes, and HTML templates
│   └── infrastructure/
│       ├── persistence/
│       │   └── database.py              # SQLite database (users, customers)
│       ├── whatsapp/
│       │   └── selenium_provider.py     # WhatsApp Web automation via Selenium
│       ├── llm/
│       │   └── sentiment_service.py     # AI sentiment analysis via OpenRouter
│       ├── scraper/
│       │   └── business_scraper.py      # Google Maps data scraper
│       ├── importer/
│       │   └── excel_parser.py          # Excel/CSV import parser
│       └── config/                      # Settings and environment config
└── whatsapp_profile/                    # Chrome session data (persists QR login)
```

---

## Tech Stack

| Layer         | Technology                     |
|---------------|--------------------------------|
| Web Framework | FastAPI + Uvicorn              |
| Database      | SQLite                         |
| WhatsApp      | Selenium + Chrome WebDriver    |
| Sentiment AI  | OpenRouter API (LLM)           |
| Scraping      | Requests + BeautifulSoup       |
| Frontend      | Inline HTML/CSS (Glassmorphism)|

---

## Configuration

| Variable             | Description                              | Required |
|----------------------|------------------------------------------|----------|
| `GOOGLE_REVIEW_LINK` | Your Google Review URL                   | Yes      |
| `OPENROUTER_API_KEY`  | API key for LLM sentiment analysis       | Optional |

---

## License

MIT
