"""
FastAPI Web Application - Review Master Dashboard
==================================================

Web UI for managing customers and sending review requests.
Features per-user data isolation and a modern glassmorphism UI.
"""

import os
import io
import logging
import hashlib
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Form, BackgroundTasks, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.infrastructure.persistence import Database, init_with_test_data, User
from src.infrastructure.config import get_settings
from src.infrastructure.scraper import BusinessScraper
from src.infrastructure.importer.excel_parser import ExcelParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Globals ────────────────────────────────────────────────────────
db: Optional[Database] = None
scraper = BusinessScraper()
whatsapp_client = None
whatsapp_ready = False

# ── Message Templates ──────────────────────────────────────────────
TEST_MESSAGE_TEMPLATE = "Hi {name}, thank you for purchasing {product} from us! We hope you're enjoying it. If you have a moment, we'd love to hear your feedback."
REVIEW_REQUEST_TEMPLATE = "Hi {name}, we noticed you recently purchased {product}. We hope you're satisfied with your purchase! Would you mind sharing a quick review about your experience?"
GOOGLE_LINK_TEMPLATE = "Thank you so much for your kind words, {name}! We really appreciate it. If you have a moment, we would be grateful if you could share your experience on Google: {link}"
THANK_YOU_TEMPLATE = "Thank you for your feedback, {name}. We appreciate you taking the time to share your thoughts with us. If there's anything we can do to improve, please let us know!"


def get_google_link():
    try:
        settings = get_settings()
        return settings.review.google_review_link
    except Exception:
        return "https://g.page/review/YOUR_BUSINESS"


# ── Lifespan ───────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db
    db = init_with_test_data()
    logger.info("Database ready")
    yield


app = FastAPI(title="Review Master", description="WhatsApp Review Collection System", lifespan=lifespan)


# ══════════════════════════════════════════════════════════════════
#  SHARED CSS — reused across all pages
# ══════════════════════════════════════════════════════════════════

SHARED_CSS = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    :root {
        --bg-dark: #0a0a14;
        --bg-card: rgba(255,255,255,0.035);
        --bg-card-hover: rgba(255,255,255,0.06);
        --border: rgba(255,255,255,0.07);
        --border-hover: rgba(124,58,237,0.4);
        --text: #e2e8f0;
        --text-muted: #64748b;
        --accent-1: #7c3aed;
        --accent-2: #06b6d4;
        --accent-3: #8b5cf6;
        --gradient: linear-gradient(135deg, #7c3aed 0%, #06b6d4 100%);
        --gradient-subtle: linear-gradient(135deg, rgba(124,58,237,0.15), rgba(6,182,212,0.10));
    }

    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background: var(--bg-dark);
        background-image:
            radial-gradient(ellipse 80% 50% at 50% -20%, rgba(124,58,237,0.15), transparent),
            radial-gradient(ellipse 60% 40% at 80% 100%, rgba(6,182,212,0.08), transparent);
        min-height: 100vh;
        color: var(--text);
    }

    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
        from { opacity: 0; }
        to   { opacity: 1; }
    }
    @keyframes shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    @keyframes pulse-glow {
        0%, 100% { box-shadow: 0 0 20px rgba(124,58,237,0.1); }
        50% { box-shadow: 0 0 30px rgba(124,58,237,0.2); }
    }

    .card {
        background: var(--bg-card);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 28px;
        transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
        animation: fadeInUp 0.5s ease-out both;
    }
    .card:hover {
        border-color: var(--border-hover);
        box-shadow: 0 8px 32px rgba(124,58,237,0.08);
    }

    .btn {
        background: var(--gradient);
        color: #fff;
        border: none;
        padding: 12px 28px;
        border-radius: 10px;
        font-weight: 600;
        font-size: 14px;
        cursor: pointer;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        transition: all 0.25s ease;
        font-family: inherit;
    }
    .btn:hover { opacity: 0.9; transform: translateY(-1px); box-shadow: 0 4px 20px rgba(124,58,237,0.3); }
    .btn:active { transform: translateY(0); }

    .btn-ghost {
        background: var(--bg-card);
        border: 1px solid var(--border);
        color: var(--text);
    }
    .btn-ghost:hover { background: var(--bg-card-hover); border-color: var(--border-hover); box-shadow: none; }

    .badge {
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 10px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.4px;
    }
    .badge.pending  { background: rgba(139,92,246,0.15); color: #a78bfa; }
    .badge.done     { background: rgba(52,211,153,0.15); color: #34d399; }
    .badge.no-reply { background: rgba(251,191,36,0.15); color: #fbbf24; }
    .badge.error    { background: rgba(248,113,113,0.15); color: #f87171; }
    .badge.positive { background: rgba(52,211,153,0.15); color: #34d399; }
    .badge.neutral  { background: rgba(148,163,184,0.15); color: #94a3b8; }
    .badge.negative { background: rgba(252,165,165,0.15); color: #fca5a5; }

    input[type="text"], input[type="password"], input[type="email"], select {
        background: rgba(255,255,255,0.05);
        border: 1px solid var(--border);
        padding: 12px 16px;
        border-radius: 10px;
        color: var(--text);
        font-size: 14px;
        font-family: inherit;
        width: 100%;
        transition: all 0.25s ease;
    }
    input:focus, select:focus {
        outline: none;
        border-color: var(--accent-1);
        background: rgba(255,255,255,0.07);
        box-shadow: 0 0 0 3px rgba(124,58,237,0.15);
    }

    .alert {
        padding: 14px 20px;
        border-radius: 12px;
        margin-bottom: 20px;
        font-size: 14px;
        text-align: center;
        animation: fadeIn 0.4s ease;
    }
    .alert-info {
        background: rgba(124,58,237,0.1);
        border: 1px solid rgba(124,58,237,0.25);
        color: #a78bfa;
    }
    .alert-success {
        background: rgba(52,211,153,0.1);
        border: 1px solid rgba(52,211,153,0.25);
        color: #34d399;
    }
    .alert-error {
        background: rgba(248,113,113,0.1);
        border: 1px solid rgba(248,113,113,0.25);
        color: #f87171;
    }

    a { color: var(--accent-2); text-decoration: none; transition: color 0.2s; }
    a:hover { color: #22d3ee; }

    code {
        background: rgba(255,255,255,0.06);
        padding: 2px 7px;
        border-radius: 5px;
        font-size: 12px;
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
    }
"""


# ══════════════════════════════════════════════════════════════════
#  HTML TEMPLATE RENDERERS
# ══════════════════════════════════════════════════════════════════

def render_login_page(message: str = "") -> str:
    msg_html = f'<div class="alert alert-error">{message}</div>' if message else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Review Master</title>
    <style>
        {SHARED_CSS}
        body {{ display: flex; justify-content: center; align-items: center; }}
        .auth-card {{
            width: 100%; max-width: 420px;
            padding: 44px 36px;
            animation: fadeInUp 0.6s ease-out;
        }}
        .logo {{
            text-align: center; margin-bottom: 32px;
        }}
        .logo h1 {{
            font-size: 30px; font-weight: 800;
            background: var(--gradient);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }}
        .logo p {{ color: var(--text-muted); font-size: 14px; margin-top: 6px; }}
        .form-group {{ margin-bottom: 16px; }}
        .form-group label {{ display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 6px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }}
        .btn {{ width: 100%; justify-content: center; margin-top: 8px; padding: 14px; }}
        .footer {{ text-align: center; margin-top: 24px; font-size: 13px; color: var(--text-muted); }}
    </style>
</head>
<body>
    <div class="card auth-card">
        <div class="logo">
            <h1>Review Master</h1>
            <p>Automate your review collection</p>
        </div>
        {msg_html}
        <form method="post" action="/login">
            <div class="form-group">
                <label>Email or Username</label>
                <input type="text" name="email" placeholder="you@business.com" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" placeholder="Enter password" required>
            </div>
            <button type="submit" class="btn">Sign In</button>
        </form>
        <div class="footer">
            Don't have an account? <a href="/signup">Create one</a>
        </div>
    </div>
</body>
</html>"""


def render_signup_page(message: str = "") -> str:
    msg_html = f'<div class="alert alert-error">{message}</div>' if message else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign Up - Review Master</title>
    <style>
        {SHARED_CSS}
        body {{ display: flex; justify-content: center; align-items: center; padding: 20px; }}
        .auth-card {{
            width: 100%; max-width: 440px;
            padding: 40px 36px;
            animation: fadeInUp 0.6s ease-out;
        }}
        .logo {{
            text-align: center; margin-bottom: 28px;
        }}
        .logo h1 {{
            font-size: 28px; font-weight: 800;
            background: var(--gradient);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }}
        .logo p {{ color: var(--text-muted); font-size: 14px; margin-top: 6px; }}
        .form-group {{ margin-bottom: 14px; }}
        .form-group label {{ display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 5px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }}
        .hint {{ font-size: 11px; color: var(--text-muted); margin-top: 4px; }}
        .btn {{ width: 100%; justify-content: center; margin-top: 8px; padding: 14px; }}
        .footer {{ text-align: center; margin-top: 24px; font-size: 13px; color: var(--text-muted); }}
    </style>
</head>
<body>
    <div class="card auth-card">
        <div class="logo">
            <h1>Create Account</h1>
            <p>Get started with Review Master</p>
        </div>
        {msg_html}
        <form method="post" action="/signup">
            <div class="form-group">
                <label>Email</label>
                <input type="text" name="email" placeholder="you@business.com" required>
            </div>
            <div class="form-group">
                <label>Full Name</label>
                <input type="text" name="username" placeholder="Your name" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" placeholder="Choose a password" required>
            </div>
            <div class="form-group">
                <label>Business Name</label>
                <input type="text" name="business_name" placeholder="Your Business" required>
            </div>
            <div class="form-group">
                <label>Google Maps / Search Link</label>
                <input type="text" name="business_link" placeholder="https://maps.google.com/..." required>
                <div class="hint">We'll fetch your reviews and rating from this link.</div>
            </div>
            <button type="submit" class="btn">Create Account</button>
        </form>
        <div class="footer">
            Already have an account? <a href="/login">Sign in</a>
        </div>
    </div>
</body>
</html>"""


def render_setup_page(user: User, message: str = "", error: str = "") -> str:
    msg_html = f'<div class="alert alert-success">{message}</div>' if message else ""
    err_html = f'<div class="alert alert-error">{error}</div>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Import Data - Review Master</title>
    <style>
        {SHARED_CSS}
        body {{ display: flex; align-items: center; justify-content: center; padding: 24px; }}
        .container {{ max-width: 820px; width: 100%; }}
        .header {{ text-align: center; margin-bottom: 36px; animation: fadeInUp 0.5s ease-out; }}
        .header h1 {{
            font-size: 32px; font-weight: 800;
            background: var(--gradient);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }}
        .header p {{ color: var(--text-muted); font-size: 15px; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 24px; }}
        .import-card {{ text-align: center; animation-delay: 0.15s; }}
        .import-card .icon {{ font-size: 42px; margin-bottom: 16px; }}
        .import-card h2 {{ font-size: 18px; font-weight: 600; margin-bottom: 10px; }}
        .import-card p {{ color: var(--text-muted); font-size: 13px; line-height: 1.6; margin-bottom: 20px; }}
        .upload-zone {{
            border: 2px dashed rgba(124,58,237,0.3);
            border-radius: 14px;
            padding: 28px 20px;
            margin-bottom: 18px;
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        .upload-zone:hover {{ border-color: rgba(124,58,237,0.6); background: rgba(124,58,237,0.04); }}
        .upload-zone.dragover {{ border-color: var(--accent-1); background: rgba(124,58,237,0.08); }}
        input[type="file"] {{ display: none; }}
        .file-label {{ color: var(--accent-2); cursor: pointer; font-weight: 500; font-size: 14px; }}
        .formats {{ font-size: 11px; color: var(--text-muted); margin-top: 8px; }}
        .skip {{ text-align: center; margin-top: 32px; }}
        .skip a {{ color: var(--text-muted); font-size: 13px; }}
        .skip a:hover {{ color: var(--accent-2); }}
        .btn {{ width: 100%; justify-content: center; }}
        .progress-wrap {{ display: none; margin-top: 12px; }}
        .progress-bar {{ height: 4px; border-radius: 2px; background: rgba(255,255,255,0.1); overflow: hidden; }}
        .progress-fill {{ height: 100%; width: 0%; background: var(--gradient); transition: width 0.3s; border-radius: 2px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome, {user.username}!</h1>
            <p>Import your customer data to start collecting reviews</p>
        </div>
        {msg_html}{err_html}
        <div class="cards">
            <div class="card import-card">
                <div class="icon">📊</div>
                <h2>Import Excel Sheet</h2>
                <p>Upload customer data from Excel or CSV. We auto-detect name, phone, and product columns.</p>
                <form method="post" action="/import/excel" enctype="multipart/form-data" id="upload-form">
                    <div class="upload-zone" id="drop-zone">
                        <input type="file" name="file" id="excel-file" accept=".xlsx,.xls,.csv" required>
                        <label for="excel-file" class="file-label" id="file-label">Click to choose file</label>
                        <div class="formats">Supports: .xlsx, .xls, .csv</div>
                    </div>
                    <div class="progress-wrap" id="progress-wrap">
                        <div class="progress-bar"><div class="progress-fill" id="progress-fill"></div></div>
                    </div>
                    <button type="submit" class="btn" id="upload-btn">Import Customers</button>
                </form>
            </div>
            <div class="card import-card" style="animation-delay: 0.25s;">
                <div class="icon">🔗</div>
                <h2>Connect Database</h2>
                <p>Sync customer data from an external database automatically. Coming soon!</p>
                <button class="btn btn-ghost" disabled style="opacity:0.4; width:100%; justify-content:center;">Coming Soon</button>
            </div>
        </div>
        <div class="skip"><a href="/">Skip — Go to Dashboard →</a></div>
    </div>
    <script>
        const fileInput = document.getElementById('excel-file');
        const fileLabel = document.getElementById('file-label');
        const dropZone  = document.getElementById('drop-zone');
        const form      = document.getElementById('upload-form');
        const progressW = document.getElementById('progress-wrap');
        const progressF = document.getElementById('progress-fill');
        const uploadBtn = document.getElementById('upload-btn');

        fileInput.addEventListener('change', function() {{
            if (this.files.length > 0) fileLabel.textContent = this.files[0].name;
        }});

        dropZone.addEventListener('dragover', e => {{ e.preventDefault(); dropZone.classList.add('dragover'); }});
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
        dropZone.addEventListener('drop', e => {{
            e.preventDefault(); dropZone.classList.remove('dragover');
            fileInput.files = e.dataTransfer.files;
            if (fileInput.files.length > 0) fileLabel.textContent = fileInput.files[0].name;
        }});

        form.addEventListener('submit', function() {{
            uploadBtn.textContent = 'Uploading...';
            uploadBtn.disabled = true;
            progressW.style.display = 'block';
            let w = 0;
            const iv = setInterval(() => {{ w = Math.min(w + 8, 90); progressF.style.width = w + '%'; }}, 100);
        }});
    </script>
</body>
</html>"""


def render_dashboard(stats: dict, customers: list, recent: list, user: User, message: str = "", whatsapp_status: str = "Not Connected") -> str:
    """Render the main dashboard with modern glassmorphism UI."""

    # Customer dropdown options
    customer_options = "".join([
        f'<option value="{c.id}">{c.name} - {c.product or "No Product"} ({c.phone})</option>'
        for c in customers
    ])

    # Top 5 pending customers
    pending_customers = [c for c in customers if c.status == "pending"][:5]
    quick_cards = ""
    for i, c in enumerate(pending_customers):
        quick_cards += f"""
        <div class="quick-card" style="animation-delay: {0.1 * i}s;">
            <div class="quick-info">
                <div class="quick-name">{c.name}</div>
                <div class="quick-meta">{c.product or 'No product'} · {c.phone}</div>
            </div>
            <form method="post" action="/customer/{c.id}/request-review">
                <button type="submit" class="btn btn-sm">Request Review</button>
            </form>
        </div>"""
    if not quick_cards:
        quick_cards = '<div class="empty-state">No pending customers. Import data to get started!</div>'

    # Recent uploads preview (3-4 entries)
    recent_rows = ""
    for c in recent:
        recent_rows += f"""
        <div class="recent-item">
            <div class="recent-avatar">{c.name[0].upper()}</div>
            <div class="recent-info">
                <div class="recent-name">{c.name}</div>
                <div class="recent-meta">{c.product or 'N/A'} · <code>{c.phone}</code></div>
            </div>
        </div>"""
    if not recent_rows:
        recent_rows = '<div class="empty-state" style="padding: 20px;">No data uploaded yet. <a href="/setup">Import now</a></div>'

    # All customers table
    table_rows = ""
    for c in customers:
        status_badge = {
            "pending": '<span class="badge pending">Pending</span>',
            "done": '<span class="badge done">Done</span>',
            "no_reply": '<span class="badge no-reply">No Reply</span>',
            "error": '<span class="badge error">Error</span>',
        }.get(c.status, c.status)

        sentiment_badge = ""
        if c.sentiment:
            cls = {"Positive": "positive", "Neutral": "neutral", "Negative": "negative"}.get(c.sentiment, "")
            sentiment_badge = f'<span class="badge {cls}">{c.sentiment}</span>'

        table_rows += f"""
        <tr>
            <td><strong>{c.name}</strong></td>
            <td><code>{c.phone}</code></td>
            <td>{c.product or '<span style="color:var(--text-muted)">—</span>'}</td>
            <td>{status_badge}</td>
            <td>{sentiment_badge or '<span style="color:var(--text-muted)">—</span>'}</td>
            <td class="actions-cell">
                <form method="post" action="/customer/{c.id}/request-review" style="display:inline"><button type="submit" class="btn-tiny btn-accent">Request</button></form>
                <form method="post" action="/customer/{c.id}/send-test" style="display:inline"><button type="submit" class="btn-tiny btn-cyan">Test</button></form>
                <form method="post" action="/customer/{c.id}/delete" style="display:inline"><button type="submit" class="btn-tiny btn-red">✕</button></form>
            </td>
        </tr>"""

    msg_html = f'<div class="alert alert-info">{message}</div>' if message else ""
    wa_badge = '<span class="badge done">Connected</span>' if whatsapp_status == "Connected" else '<span class="badge pending">Offline</span>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Review Master</title>
    <style>
        {SHARED_CSS}

        .container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}

        /* ── Header ─── */
        header {{
            display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;
            padding: 20px 28px; margin-bottom: 28px;
            animation: fadeInUp 0.4s ease-out;
        }}
        header h1 {{
            font-size: 26px; font-weight: 800;
            background: var(--gradient);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }}
        .header-sub {{ font-size: 13px; color: var(--text-muted); margin-top: 4px; }}
        .header-actions {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
        .wa-status {{ display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-muted); }}

        /* ── Stats Grid ─── */
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 28px; }}
        .stat {{
            text-align: center; padding: 22px 16px;
            animation: fadeInUp 0.5s ease-out both;
        }}
        .stat:nth-child(1) {{ animation-delay: 0.05s; }}
        .stat:nth-child(2) {{ animation-delay: 0.1s; }}
        .stat:nth-child(3) {{ animation-delay: 0.15s; }}
        .stat:nth-child(4) {{ animation-delay: 0.2s; }}
        .stat:nth-child(5) {{ animation-delay: 0.25s; }}
        .stat-val {{
            font-size: 30px; font-weight: 800;
            background: var(--gradient);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }}
        .stat-label {{ font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 6px; }}

        /* ── Business Analytics ─── */
        .analytics {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 20px;
            text-align: center; padding: 4px 0;
        }}
        .analytics-val {{ font-size: 26px; font-weight: 700; color: #fff; }}
        .analytics-label {{ font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 5px; }}
        .analytics-text {{ font-size: 13px; color: var(--text); margin-bottom: 4px; }}

        /* ── Section titles ─── */
        .section-title {{ font-size: 17px; font-weight: 600; margin-bottom: 18px; display: flex; align-items: center; gap: 10px; }}

        /* ── Quick Actions ─── */
        .quick-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }}
        .quick-card {{
            background: var(--gradient-subtle);
            border: 1px solid rgba(124,58,237,0.12);
            border-radius: 14px;
            padding: 18px 20px;
            display: flex; justify-content: space-between; align-items: center; gap: 14px;
            transition: all 0.3s ease;
            animation: fadeInUp 0.5s ease-out both;
        }}
        .quick-card:hover {{ border-color: rgba(124,58,237,0.35); transform: translateY(-2px); box-shadow: 0 6px 24px rgba(124,58,237,0.1); }}
        .quick-name {{ font-weight: 600; font-size: 14px; }}
        .quick-meta {{ font-size: 11px; color: var(--text-muted); margin-top: 3px; }}
        .btn-sm {{ padding: 8px 18px; font-size: 12px; border-radius: 8px; white-space: nowrap; }}

        /* ── Recent Uploads ─── */
        .recent-list {{ display: flex; flex-direction: column; gap: 10px; }}
        .recent-item {{
            display: flex; align-items: center; gap: 14px;
            padding: 12px 16px;
            background: rgba(255,255,255,0.02);
            border-radius: 10px;
            transition: background 0.2s;
        }}
        .recent-item:hover {{ background: rgba(255,255,255,0.04); }}
        .recent-avatar {{
            width: 36px; height: 36px;
            border-radius: 10px;
            background: var(--gradient);
            display: flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 14px; color: #fff;
            flex-shrink: 0;
        }}
        .recent-name {{ font-weight: 500; font-size: 14px; }}
        .recent-meta {{ font-size: 11px; color: var(--text-muted); margin-top: 2px; }}

        /* ── Two-col layout ─── */
        .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }}
        @media (max-width: 900px) {{ .two-col {{ grid-template-columns: 1fr; }} }}

        /* ── Three-col layout ─── */
        .three-col {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px; margin-bottom: 24px; }}
        @media (max-width: 1100px) {{ .three-col {{ grid-template-columns: 1fr 1fr; }} }}
        @media (max-width: 700px) {{ .three-col {{ grid-template-columns: 1fr; }} }}

        /* ── Table ─── */
        .table-wrap {{ max-height: 420px; overflow-y: auto; border-radius: 12px; }}
        .table-wrap::-webkit-scrollbar {{ width: 5px; }}
        .table-wrap::-webkit-scrollbar-track {{ background: transparent; }}
        .table-wrap::-webkit-scrollbar-thumb {{ background: rgba(124,58,237,0.25); border-radius: 3px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ padding: 12px; text-align: left; color: var(--text-muted); font-weight: 500; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; background: rgba(0,0,0,0.25); position: sticky; top: 0; z-index: 5; }}
        td {{ padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.03); font-size: 13px; }}
        tr:hover td {{ background: rgba(255,255,255,0.02); }}
        .actions-cell {{ white-space: nowrap; }}

        .btn-tiny {{
            background: rgba(255,255,255,0.06); color: var(--text); border: none;
            padding: 5px 10px; border-radius: 6px; cursor: pointer; font-size: 10px; font-weight: 500;
            transition: all 0.2s; font-family: inherit; margin-right: 2px;
        }}
        .btn-tiny:hover {{ background: rgba(255,255,255,0.12); }}
        .btn-accent {{ background: rgba(124,58,237,0.15); color: #a78bfa; }}
        .btn-accent:hover {{ background: rgba(124,58,237,0.25); }}
        .btn-cyan {{ background: rgba(6,182,212,0.15); color: #22d3ee; }}
        .btn-cyan:hover {{ background: rgba(6,182,212,0.25); }}
        .btn-red {{ background: rgba(239,68,68,0.12); color: #f87171; }}
        .btn-red:hover {{ background: rgba(239,68,68,0.22); }}

        .empty-state {{ text-align: center; padding: 36px; color: var(--text-muted); font-size: 13px; }}

        /* ── Form rows ─── */
        .form-stack {{ display: flex; flex-direction: column; gap: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <header class="card">
            <div>
                <h1>Review Master</h1>
                <div class="header-sub">{user.business_name} · <a href="{user.business_link}" target="_blank">View Listing</a></div>
            </div>
            <div class="header-actions">
                <div class="wa-status">WhatsApp: {wa_badge}</div>
                <a href="/setup" class="btn btn-ghost">Import Data</a>
                <a href="/whatsapp/connect" class="btn btn-ghost">Connect WhatsApp</a>
                <a href="/logout" class="btn btn-ghost" style="opacity:0.7;">Logout</a>
            </div>
        </header>

        {msg_html}

        <!-- Business Analytics -->
        <div class="card" style="margin-bottom: 24px; animation-delay: 0.1s;">
            <div class="section-title">📊 Business Analytics</div>
            <div class="analytics">
                <div><div class="analytics-val">{user.rating} ⭐</div><div class="analytics-label">Google Rating</div></div>
                <div><div class="analytics-val">{user.total_reviews}</div><div class="analytics-label">Total Reviews</div></div>
                <div><div class="analytics-text">{user.location or 'N/A'}</div><div class="analytics-label">Location</div></div>
                <div><div class="analytics-text">{user.contact_info or 'N/A'}</div><div class="analytics-label">Contact</div></div>
            </div>
        </div>

        <!-- Stats -->
        <div class="stats">
            <div class="card stat"><div class="stat-val">{stats['total']}</div><div class="stat-label">Total Customers</div></div>
            <div class="card stat"><div class="stat-val">{stats['pending']}</div><div class="stat-label">Pending</div></div>
            <div class="card stat"><div class="stat-val">{stats['done']}</div><div class="stat-label">Completed</div></div>
            <div class="card stat"><div class="stat-val">{stats['positive']}</div><div class="stat-label">Positive</div></div>
            <div class="card stat"><div class="stat-val">{stats['conversion_rate']}%</div><div class="stat-label">Conversion</div></div>
        </div>

        <!-- Quick Actions -->
        <div class="card" style="margin-bottom: 24px; animation-delay: 0.2s;">
            <div class="section-title">⚡ Quick Actions — Top 5 Pending</div>
            <div class="quick-grid">{quick_cards}</div>
        </div>

        <!-- Three-col: Recent | Add Customer | Send Test -->
        <div class="three-col">
            <div class="card" style="animation-delay: 0.25s;">
                <div class="section-title">📋 Recent Uploads</div>
                <div class="recent-list">{recent_rows}</div>
            </div>
            <div class="card" style="animation-delay: 0.3s;">
                <div class="section-title">➕ Add Customer</div>
                <form method="post" action="/customer/add" class="form-stack">
                    <input type="text" name="name" placeholder="Customer Name" required>
                    <input type="text" name="phone" placeholder="Phone (e.g. 923001234567)" required>
                    <input type="text" name="product" placeholder="Product (e.g. iPhone 15)" required>
                    <button type="submit" class="btn" style="width:100%; justify-content:center;">+ Add Customer</button>
                </form>
            </div>
            <div class="card" style="animation-delay: 0.35s;">
                <div class="section-title">🧪 Send Test Message</div>
                <p style="color:var(--text-muted); margin-bottom:14px; font-size:12px;">Send a single test message to verify WhatsApp is working.</p>
                <form method="post" action="/send-test" class="form-stack">
                    <select name="customer_id" required>
                        <option value="">— Select Customer —</option>
                        {customer_options}
                    </select>
                    <button type="submit" class="btn" style="width:100%; justify-content:center;">Send Test</button>
                </form>
            </div>
        </div>

        <!-- All Customers -->
        <div class="card" style="animation-delay: 0.35s;">
            <div class="section-title">👥 All Customers ({stats['total']})</div>
            <div class="table-wrap">
                <table>
                    <thead><tr><th>Name</th><th>Phone</th><th>Product</th><th>Status</th><th>Sentiment</th><th>Actions</th></tr></thead>
                    <tbody>
                        {table_rows if table_rows else '<tr><td colspan="6" class="empty-state">No customers yet. <a href="/setup">Import data</a> or add one above!</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>"""


def render_whatsapp_connect_page(message: str = "") -> str:
    msg_html = f'<div class="alert alert-info">{message}</div>' if message else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Connect WhatsApp - Review Master</title>
    <style>
        {SHARED_CSS}
        body {{ display: flex; align-items: center; justify-content: center; }}
        .connect-card {{ max-width: 500px; text-align: center; padding: 40px; animation: fadeInUp 0.6s ease-out; }}
        .connect-card h1 {{
            font-size: 26px; font-weight: 800; margin-bottom: 16px;
            background: var(--gradient);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }}
        .connect-card p {{ color: var(--text-muted); margin-bottom: 24px; line-height: 1.6; font-size: 14px; }}
        .steps {{ text-align: left; margin: 20px 0 28px; padding-left: 20px; }}
        .steps li {{ margin: 10px 0; color: var(--text); font-size: 14px; line-height: 1.5; }}
        .btn {{ margin: 6px; }}
    </style>
</head>
<body>
    <div class="card connect-card">
        <h1>Connect WhatsApp</h1>
        {msg_html}
        <p>Link your WhatsApp to send messages and collect reviews.</p>
        <ol class="steps">
            <li>Click <strong>Launch WhatsApp</strong> below</li>
            <li>A Chrome browser will open with WhatsApp Web</li>
            <li>Scan the QR code with your phone</li>
            <li>Wait for chats to load</li>
            <li>Come back and click <strong>I'm Connected</strong></li>
        </ol>
        <form method="post" action="/whatsapp/launch" style="display:inline">
            <button type="submit" class="btn">Launch WhatsApp</button>
        </form>
        <form method="post" action="/whatsapp/confirm" style="display:inline">
            <button type="submit" class="btn btn-ghost">I'm Connected</button>
        </form>
        <div style="margin-top: 20px;"><a href="/" class="btn btn-ghost" style="opacity: 0.7;">← Back to Dashboard</a></div>
    </div>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════

def scrape_business_info(user_id: int, url: str):
    """Background task to scrape business info."""
    try:
        logger.info(f"Starting background scrape for user {user_id}...")
        info = scraper.scrape(url)
        db.update_user_analytics(
            user_id,
            total_reviews=info["total_reviews"],
            rating=info["rating"],
            location=info["location"],
            contact_info=info["contact_info"]
        )
        logger.info(f"Background scrape completed for user {user_id}")
    except Exception as e:
        logger.exception(f"Background scrape failed for user {user_id}: {e}")


# ── Auth helpers ───────────────────────────────────────────────

def _get_current_user(request: Request):
    """Get logged-in user from cookie, or None."""
    uid = request.cookies.get("user_id")
    if not uid:
        return None
    return db.get_user_by_id(int(uid))


# ── Auth routes ────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(message: str = ""):
    return render_login_page(message)


@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    user = db.get_user_by_email_or_username(email)
    if not user:
        return HTMLResponse(render_login_page(message="User not found"))

    hashed = hashlib.sha256(password.encode()).hexdigest()
    if hashed != user.password_hash:
        return HTMLResponse(render_login_page(message="Invalid password"))

    response = RedirectResponse(url="/setup", status_code=303)
    response.set_cookie(key="user_id", value=str(user.id))
    return response


@app.get("/signup", response_class=HTMLResponse)
async def signup_page():
    return render_signup_page()


@app.post("/signup")
async def signup(
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    business_name: str = Form(...),
    business_link: str = Form(...)
):
    if db.get_user_by_email(email):
        return HTMLResponse(render_signup_page(message="Email already exists"))

    hashed = hashlib.sha256(password.encode()).hexdigest()
    user_id = db.create_user(email, username, business_name, business_link, hashed)
    if not user_id:
        return HTMLResponse(render_signup_page(message="Failed to create user"))

    background_tasks.add_task(scrape_business_info, user_id, business_link)

    response = RedirectResponse(url="/?message=Account created! Fetching business info in background...", status_code=303)
    response.set_cookie(key="user_id", value=str(user_id))
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("user_id")
    return response


# ── Setup / Import ─────────────────────────────────────────────

@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, message: str = "", error: str = ""):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    return HTMLResponse(render_setup_page(user, message, error))


@app.post("/import/excel")
async def import_excel(request: Request, file: UploadFile = File(...)):
    """Import customers from Excel/CSV — fast in-memory processing."""
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    if not file.filename:
        return RedirectResponse(url="/setup?error=No file selected", status_code=303)

    ext = Path(file.filename).suffix.lower()
    if ext not in ['.xlsx', '.xls', '.csv']:
        return RedirectResponse(url="/setup?error=Invalid file type. Use .xlsx, .xls, or .csv", status_code=303)

    try:
        # Fast: read entire file into memory (no temp file)
        content = await file.read()
        buffer = io.BytesIO(content)

        # Parse using pandas via ExcelParser (pass the BytesIO buffer)
        import pandas as pd
        if ext == '.csv':
            df = pd.read_csv(buffer)
        else:
            df = pd.read_excel(buffer, sheet_name=0)

        # Use ExcelParser's column detection logic
        parser = ExcelParser()
        df.columns = df.columns.str.strip().str.lower()

        from src.infrastructure.importer.excel_parser import NAME_PATTERNS, PHONE_PATTERNS, PRODUCT_PATTERNS
        name_col = parser._find_column(df.columns, NAME_PATTERNS)
        phone_col = parser._find_column(df.columns, PHONE_PATTERNS)
        product_col = parser._find_column(df.columns, PRODUCT_PATTERNS)

        if not name_col:
            return RedirectResponse(url="/setup?error=Could not detect Name column", status_code=303)
        if not phone_col:
            return RedirectResponse(url="/setup?error=Could not detect Phone column", status_code=303)

        customers = []
        for _, row in df.iterrows():
            name = str(row.get(name_col, '')).strip()
            phone = parser._clean_phone(str(row.get(phone_col, '')))
            product = str(row.get(product_col, '')) if product_col else ''
            if not name or name.lower() == 'nan' or not phone:
                continue
            if product.lower() == 'nan':
                product = ''
            customers.append({'name': name, 'phone': phone, 'product': product.strip()})

        if not customers:
            return RedirectResponse(url="/setup?error=No valid customers found in file", status_code=303)

        # Bulk import with user_id
        result = db.bulk_add_customers(user.id, customers)

        message = f"Imported {result['added']} customers!"
        if result['skipped'] > 0:
            message += f" ({result['skipped']} duplicates skipped)"

        return RedirectResponse(url=f"/?message={message}", status_code=303)

    except ValueError as e:
        return RedirectResponse(url=f"/setup?error={str(e)}", status_code=303)
    except Exception as e:
        logger.exception(f"Excel import error: {e}")
        return RedirectResponse(url=f"/setup?error=Import failed: {str(e)[:80]}", status_code=303)


# ── Dashboard ──────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, message: str = ""):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    stats = db.get_stats(user_id=user.id)
    customers = db.get_all_customers(user_id=user.id)
    recent = db.get_recent_customers(user_id=user.id, limit=4)
    status = "Connected" if whatsapp_ready else "Not Connected"
    return render_dashboard(stats, customers, recent, user, message, status)


# ── Customer CRUD ──────────────────────────────────────────────

@app.post("/customer/add")
async def add_customer(request: Request, name: str = Form(...), phone: str = Form(...), product: str = Form(...)):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    phone = phone.replace(" ", "").replace("-", "").replace("+", "")
    result = db.add_customer(user.id, name, phone, product)
    if result:
        return RedirectResponse(url="/?message=Customer added successfully", status_code=303)
    return RedirectResponse(url="/?message=Customer already exists", status_code=303)


@app.post("/customer/{customer_id}/delete")
async def delete_customer(customer_id: int):
    db.delete_customer(customer_id)
    return RedirectResponse(url="/?message=Customer deleted", status_code=303)


@app.post("/customer/{customer_id}/reset")
async def reset_customer(customer_id: int):
    db.reset_customer(customer_id)
    return RedirectResponse(url="/?message=Customer reset to pending", status_code=303)


@app.post("/customer/{customer_id}/send-test")
async def send_test_to_customer(customer_id: int):
    return await send_test_message(customer_id)


@app.post("/send-test")
async def send_test_message(customer_id: int = Form(...)):
    """Send a single test message to selected customer."""
    global whatsapp_client, whatsapp_ready

    customer = db.get_customer(customer_id)
    if not customer:
        return RedirectResponse(url="/?message=Customer not found", status_code=303)

    if not whatsapp_ready or not whatsapp_client:
        return RedirectResponse(url="/?message=WhatsApp not connected. Click 'Connect WhatsApp' first.", status_code=303)

    try:
        product_name = customer.product or "your recent purchase"
        message = TEST_MESSAGE_TEMPLATE.format(name=customer.name, product=product_name)

        if whatsapp_client.open_chat(customer.phone):
            if whatsapp_client.send_message(message):
                db.update_customer(customer_id, last_message=f"Test: {message[:50]}...")
                return RedirectResponse(url=f"/?message=Test message sent to {customer.name}!", status_code=303)
            else:
                return RedirectResponse(url=f"/?message=Failed to send message to {customer.name}", status_code=303)
        else:
            return RedirectResponse(url=f"/?message=Could not open chat with {customer.name}", status_code=303)
    except Exception as e:
        logger.exception(f"Error sending test message: {e}")
        return RedirectResponse(url=f"/?message=Error: {str(e)[:50]}", status_code=303)


# ── Review Flow ────────────────────────────────────────────────

@app.post("/customer/{customer_id}/request-review")
async def request_review(customer_id: int):
    """Full review flow: request → wait → analyze → respond → update."""
    global whatsapp_client, whatsapp_ready

    customer = db.get_customer(customer_id)
    if not customer:
        return RedirectResponse(url="/?message=Customer not found", status_code=303)

    if not whatsapp_ready or not whatsapp_client:
        return RedirectResponse(url="/?message=WhatsApp not connected. Click 'Connect WhatsApp' first.", status_code=303)

    try:
        product_name = customer.product or "your recent purchase"
        request_msg = REVIEW_REQUEST_TEMPLATE.format(name=customer.name, product=product_name)

        if not whatsapp_client.open_chat(customer.phone):
            return RedirectResponse(url=f"/?message=Could not open chat with {customer.name}", status_code=303)

        if not whatsapp_client.send_message(request_msg):
            db.mark_error(customer_id, "Failed to send request")
            return RedirectResponse(url=f"/?message=Failed to send message to {customer.name}", status_code=303)

        logger.info(f"Review request sent to {customer.name}, waiting for reply...")

        reply = whatsapp_client.wait_for_reply(timeout=30, poll_interval=3)

        if not reply:
            db.mark_no_reply(customer_id)
            return RedirectResponse(url=f"/?message={customer.name}: No reply received (marked as no-reply)", status_code=303)

        logger.info(f"Got reply from {customer.name}: {reply[:50]}...")

        sentiment = analyze_sentiment(reply)
        logger.info(f"Sentiment: {sentiment}")

        if sentiment == "Positive":
            google_link = get_google_link()
            response_msg = GOOGLE_LINK_TEMPLATE.format(name=customer.name, link=google_link)
        else:
            response_msg = THANK_YOU_TEMPLATE.format(name=customer.name)

        whatsapp_client.send_message(response_msg)
        db.mark_done(customer_id, sentiment=sentiment, last_message=reply[:100])

        return RedirectResponse(url=f"/?message=Flow complete for {customer.name}! Sentiment: {sentiment}", status_code=303)

    except Exception as e:
        logger.exception(f"Error in review flow: {e}")
        db.mark_error(customer_id, str(e)[:50])
        return RedirectResponse(url=f"/?message=Error: {str(e)[:50]}", status_code=303)


def analyze_sentiment(text: str) -> str:
    """Simple keyword-based sentiment analysis. For production, use SentimentService with LLM."""
    text_lower = text.lower()

    positive_words = ["great", "good", "excellent", "amazing", "love", "happy", "thank", "perfect",
                      "awesome", "fantastic", "wonderful", "best", "satisfied", "pleased", "yes"]
    negative_words = ["bad", "terrible", "awful", "hate", "disappointed", "poor", "worst",
                      "horrible", "angry", "frustrated", "no", "never", "problem", "issue"]

    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)

    if positive_count > negative_count:
        return "Positive"
    elif negative_count > positive_count:
        return "Negative"
    else:
        return "Neutral"


# ── WhatsApp Connection ───────────────────────────────────────

@app.get("/whatsapp/connect", response_class=HTMLResponse)
async def whatsapp_connect_page(message: str = ""):
    return render_whatsapp_connect_page(message)


@app.post("/whatsapp/launch")
async def launch_whatsapp():
    global whatsapp_client, whatsapp_ready
    try:
        from src.infrastructure.whatsapp import WhatsAppClient

        if whatsapp_client:
            try:
                whatsapp_client.close()
            except Exception:
                pass

        whatsapp_client = WhatsAppClient(headless=False)
        whatsapp_ready = False

        return RedirectResponse(url="/whatsapp/connect?message=WhatsApp launched! Scan QR code, then click 'I'm Connected'", status_code=303)
    except Exception as e:
        logger.exception(f"Failed to launch WhatsApp: {e}")
        return RedirectResponse(url=f"/whatsapp/connect?message=Failed to launch: {str(e)[:50]}", status_code=303)


@app.post("/whatsapp/confirm")
async def confirm_whatsapp_connection():
    global whatsapp_client, whatsapp_ready

    if not whatsapp_client:
        return RedirectResponse(url="/whatsapp/connect?message=Launch WhatsApp first", status_code=303)

    try:
        if whatsapp_client.wait_for_login(timeout=5):
            whatsapp_ready = True
            return RedirectResponse(url="/?message=WhatsApp connected! You can now send messages.", status_code=303)
        else:
            return RedirectResponse(url="/whatsapp/connect?message=WhatsApp not ready. Make sure you scanned the QR code.", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/whatsapp/connect?message=Connection check failed: {str(e)[:30]}", status_code=303)


# ── API Endpoints ──────────────────────────────────────────────

@app.get("/api/customers")
async def api_list_customers(request: Request):
    user = _get_current_user(request)
    user_id = user.id if user else None
    customers = db.get_all_customers(user_id=user_id)
    return {"customers": [c.__dict__ for c in customers]}


@app.get("/api/stats")
async def api_stats(request: Request):
    user = _get_current_user(request)
    user_id = user.id if user else None
    return db.get_stats(user_id=user_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
