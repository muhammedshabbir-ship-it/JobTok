"""
JobTok - LinkedIn x TikTok hiring app built with Streamlit.

TikTok side   : vertical video feed of 30-second pitches (people AND jobs),
                scroll or swipe, likes, comments.
LinkedIn side : full profiles (photo, headline, experience, skills), company pages,
                connections, posts, job board + applications, messaging,
                notifications, profile strength.

Run:  streamlit run app.py
"""
import base64
import hashlib
import hmac
import html
import os
import re
import secrets
import shutil
import smtplib
import sqlite3
import ssl
import tempfile
import time
import uuid
from email.message import EmailMessage
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

try:                                   # only needed when you use a cloud database (DATABASE_URL)
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
except ImportError:                    # local SQLite mode works without it
    psycopg2 = None

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
DB_PATH = "jobtok.db"
UPLOAD_DIR = Path("static")   # served by Streamlit at /app/static (see .streamlit/config.toml)
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_SECONDS = 30
PAGE_SIZE = 5
CATEGORIES = [
    "Software / IT", "Design / Creative", "Marketing / Sales", "Finance / Accounting",
    "Customer Support", "Education / Training", "Healthcare", "Engineering / Technical",
    "Admin / Office", "Other",
]
JOB_TYPES = ["Full-time", "Part-time", "Contract", "Internship", "Remote"]
STATUSES = ["Applied", "Shortlisted", "Interview", "Hired", "Rejected"]
COMPANY_SIZES = ["1-10", "11-50", "51-200", "201-1000", "1000+"]

st.set_page_config(page_title="JobTok", page_icon="🎬", layout="centered", initial_sidebar_state="collapsed")

# ----------------------------------------------------------------------------
# Styling
# ----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .stApp { background: #000; color: #fff; }
    [data-testid="stSidebar"] { background: #121212; }
    .block-container { max-width: 760px; padding-top: 3.2rem; }
    h1, h2, h3, label, p, span, div { color: #fff; }
    .logo { font-size: 2rem; font-weight: 800; text-align: center;
            background: linear-gradient(90deg,#25f4ee,#fe2c55);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .tagline { text-align:center; color:#aaa; margin-bottom: .8rem; }
    .info-card { background: linear-gradient(180deg, rgba(0,0,0,0) 0%, #161616 40%);
                 border-radius: 0 0 18px 18px; padding: 12px 8px 4px 8px; }
    .phead { display:flex; align-items:center; gap:12px; margin: 6px 0; }
    .av { border-radius:50%; background: linear-gradient(135deg,#25f4ee,#fe2c55);
          display:flex; align-items:center; justify-content:center; font-weight:800; color:#000; flex:none; }
    .name { font-size: 1.1rem; font-weight: 700; margin: 0; }
    .sub { color:#25f4ee; font-weight:600; font-size:.9rem; }
    .meta { color:#bbb; font-size:.85rem; margin: 3px 0; }
    .jtitle { font-size:1.25rem; font-weight:800; margin: 6px 0 2px 0; }
    .chip { display:inline-block; background:#2a2a2a; color:#fff; border-radius: 14px;
            padding: 2px 10px; margin: 2px 4px 2px 0; font-size: .78rem; }
    .chip.hot { background:#fe2c55; }
    .badge { display:inline-block; background:#0a7d3c; border-radius:10px; padding:1px 8px;
             margin-left:8px; font-size:.7rem; font-weight:700; vertical-align:middle; }
    .badge.co { background:#0a66c2; }
    .st-Applied{background:#444} .st-Shortlisted{background:#0a66c2} .st-Interview{background:#b8860b}
    .st-Hired{background:#0a7d3c} .st-Rejected{background:#8b1a2b}
    .counter { text-align:center; color:#888; font-size:.85rem; margin-bottom:4px; }
    .body { background:#161616; border-radius:12px; padding:10px 12px; margin:6px 0; line-height:1.45; }
    .bubble { max-width:80%; padding:8px 12px; border-radius:16px; margin:4px 0; line-height:1.35; }
    .me { background:#fe2c55; margin-left:auto; border-bottom-right-radius:4px; }
    .them { background:#2a2a2a; margin-right:auto; border-bottom-left-radius:4px; }
    .time { font-size:.65rem; color:#ddd; opacity:.7; }
    div[data-testid="stVideo"] video { border-radius: 18px 18px 0 0; max-height: 520px; background:#111; }
    .stButton > button { border-radius: 30px; font-weight: 700; width: 100%; }

    </style>
    """,
    unsafe_allow_html=True,
)

def nav_style():
    """Pill-style top navigation bar + pill toggles (styles the st.radio widgets by key)."""
    keys = ["page", "home_mode", "hp_view", "hj_view", "disc_kind"]

    def sel(tail):
        return ",".join(f".st-key-{k} {tail}" for k in keys)

    opt = 'label[data-testid="stRadioOption"], .st-key-X label[data-baseweb="radio"]'

    def each(tail_fn):
        return ",".join(tail_fn(f".st-key-{k}") for k in keys)

    css = f"""
    .st-key-page {{ position: sticky; top: 2.9rem; z-index: 999; width: 100% !important; margin-bottom: 1rem;
        padding: 6px 8px; background: rgba(20,20,20,.9); backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px); border: 1px solid #2c2c2c; border-radius: 40px;
        box-shadow: 0 8px 28px rgba(254,44,85,.20), 0 0 0 1px rgba(37,244,238,.10); }}
    {sel('[data-testid="stRadioGroup"]')}, {sel('div[role="radiogroup"]')} {{
        display: flex !important; flex-wrap: nowrap; gap: 3px; width: 100%; overflow-x: auto;
        scrollbar-width: none; justify-content: space-between; }}
    {sel('label[data-testid="stRadioOption"]')}, {sel('label[data-baseweb="radio"]')} {{
        margin: 0 !important; padding: 8px 10px; border-radius: 30px; cursor: pointer; white-space: nowrap;
        transition: all .2s ease; color: #bbb; }}
    {sel('label[data-testid="stRadioOption"] > div > div:first-child')},
    {sel('label[data-baseweb="radio"] > div:first-child')} {{ display: none !important; }}
    {sel('label[data-testid="stRadioOption"] p')} {{ font-size: .86rem; margin: 0; }}
    {sel('label[data-testid="stRadioOption"]:hover')} {{ background: #262626; transform: translateY(-1px); }}
    {sel('label[data-testid="stRadioOption"]:has(input:checked)')},
    {sel('label[data-baseweb="radio"]:has(input:checked)')} {{
        background: linear-gradient(90deg,#25f4ee,#fe2c55); box-shadow: 0 4px 14px rgba(254,44,85,.45); }}
    {sel('label[data-testid="stRadioOption"]:has(input:checked) *')},
    {sel('label[data-baseweb="radio"]:has(input:checked) *')} {{ color: #000 !important; font-weight: 800; }}
    .st-key-home_mode, .st-key-hp_view, .st-key-hj_view, .st-key-disc_kind {{
        width: fit-content !important; background: #141414; border: 1px solid #262626; border-radius: 30px;
        padding: 4px 6px; margin-bottom: .4rem; }}
    button[data-baseweb="tab"][aria-selected="true"], button[role="tab"][aria-selected="true"] {{ color: #fe2c55 !important; }}
    div[data-baseweb="tab-highlight"] {{ background-color: #fe2c55 !important; }}
    @media (max-width: 640px) {{ .st-key-page label {{ padding: 7px 8px; }} }}
    /* ---------- action rail on top of videos ---------- */
    [class*="st-key-vc_"] {{ position: relative; width: 100% !important; max-width: 420px; margin: 0 auto; }}
    [class*="st-key-rail_"] {{ position: absolute !important; right: 10px; bottom: 74px; width: 54px !important;
        z-index: 30; display: flex; flex-direction: column; gap: 8px; }}
    [class*="st-key-rail_"] [data-testid="stElementContainer"] {{ width: 100% !important; }}
    [class*="st-key-rail_"] button {{ width: 54px; height: 54px; min-height: 0; padding: 0 !important;
        border-radius: 50% !important; font-size: 1.05rem; background: rgba(0,0,0,.62) !important;
        border: 1px solid rgba(255,255,255,.28) !important; backdrop-filter: blur(6px);
        transition: transform .15s ease, background .15s ease; }}
    [class*="st-key-rail_"] button:hover {{ transform: scale(1.12); background: rgba(254,44,85,.85) !important; }}
    [class*="st-key-rail_"] button p {{ font-size: 1rem; margin: 0; }}

    /* ---------- phone layout (also used inside the Android WebView / APK) ---------- */
    @media (max-width: 640px) {{
      header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] {{ display: none !important; }}
      .block-container {{ padding: .6rem .7rem 6.8rem !important; max-width: 100% !important; }}
      .logo {{ font-size: 1.55rem; }}
      .tagline {{ font-size: .8rem; margin-bottom: .4rem; }}
      /* bottom tab bar */
      .st-key-page {{ position: fixed !important; left: 0; right: 0; bottom: 0; top: auto !important;
          width: 100vw !important; margin: 0 !important; z-index: 1000; border-radius: 20px 20px 0 0;
          padding: 6px 4px calc(6px + env(safe-area-inset-bottom)); border-left: 0; border-right: 0; border-bottom: 0;
          background: rgba(14,14,14,.96); box-shadow: 0 -6px 24px rgba(0,0,0,.6); }}
      .st-key-page [data-testid="stRadioGroup"], .st-key-page div[role="radiogroup"] {{
          overflow: visible; justify-content: space-around; gap: 2px; }}
      .st-key-page label[data-testid="stRadioOption"], .st-key-page label[data-baseweb="radio"] {{
          flex: 1 1 0; min-width: 0; padding: 5px 1px; border-radius: 14px; justify-content: center; text-align: center; }}
      .st-key-page label > div:last-child, .st-key-page label [data-testid="stMarkdownContainer"] {{ width: 100%; }}
      .st-key-page label p {{ font-size: 10px !important; line-height: 1.2; width: 40px; margin: 0 auto !important;
          text-align: center; white-space: normal; }}
      .st-key-page label p::first-line {{ font-size: 22px; }}
      /* touch-friendly controls */
      .stButton, .stDownloadButton, [data-testid="stFormSubmitButton"] {{ width: 100% !important; }}
      .stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {{
          width: 100% !important; min-height: 44px; font-size: .85rem; padding: .35rem .4rem; }}
      input, textarea, [data-baseweb="select"] {{ font-size: 16px !important; }}
      [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: .4rem !important; }}
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{ min-width: 0 !important; flex: 1 1 0 !important; width: auto !important; }}
      [class*="st-key-rail_"] {{ right: 8px; bottom: 62px; width: 46px !important; gap: 6px; }}
      [class*="st-key-rail_"] button {{ width: 46px; height: 46px; }}
      button[data-baseweb="tab"] {{ padding: .5rem .7rem; }}
      div[data-baseweb="tab-list"] {{ overflow-x: auto; scrollbar-width: none; }}
      .bubble {{ max-width: 88%; }}
    }}
    """
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Database layer
# ----------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,                 -- 'seeker' | 'company'
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    salt TEXT NOT NULL,
    pw_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS seekers(
    user_id INTEGER PRIMARY KEY,
    headline TEXT, title TEXT, category TEXT, skills TEXT, experience INTEGER,
    city TEXT, salary INTEGER, education TEXT, about TEXT, phone TEXT,
    video_path TEXT, photo_path TEXT, open_to_work INTEGER DEFAULT 1,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS companies(
    user_id INTEGER PRIMARY KEY,
    industry TEXT, size TEXT, website TEXT, city TEXT, about TEXT, photo_path TEXT
);
CREATE TABLE IF NOT EXISTS experiences(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, role TEXT, company TEXT, start TEXT, "end" TEXT, description TEXT
);
CREATE TABLE IF NOT EXISTS posts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, body TEXT, image_path TEXT, video_path TEXT,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS likes(
    kind TEXT, target_id INTEGER, user_id INTEGER,
    PRIMARY KEY(kind, target_id, user_id)
);
CREATE TABLE IF NOT EXISTS comments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT, target_id INTEGER, user_id INTEGER, body TEXT,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS jobs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER, title TEXT, category TEXT, city TEXT, job_type TEXT,
    salary_min INTEGER, salary_max INTEGER, skills TEXT, description TEXT,
    video_path TEXT, active INTEGER DEFAULT 1,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS applications(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER, seeker_id INTEGER, note TEXT, status TEXT DEFAULT 'Applied',
    seen INTEGER DEFAULT 1,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_id, seeker_id)
);
CREATE TABLE IF NOT EXISTS connections(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id INTEGER, to_id INTEGER, status TEXT DEFAULT 'pending',
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(from_id, to_id)
);
CREATE TABLE IF NOT EXISTS messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id INTEGER, to_id INTEGER, body TEXT, is_read INTEGER DEFAULT 0,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS email_codes(
    email TEXT PRIMARY KEY, salt TEXT, code_hash TEXT, expires DOUBLE PRECISION, attempts INTEGER DEFAULT 0,
    last_sent DOUBLE PRECISION, window_start DOUBLE PRECISION, sends INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions(
    token_hash TEXT PRIMARY KEY, user_id INTEGER, created DOUBLE PRECISION, expires DOUBLE PRECISION
);
CREATE TABLE IF NOT EXISTS shortlist(
    company_id INTEGER, seeker_id INTEGER,
    PRIMARY KEY(company_id, seeker_id)
);
"""


def db_url():
    """DATABASE_URL (Postgres, e.g. Supabase) makes accounts permanent. Empty = local SQLite file."""
    return _setting("DATABASE_URL")


INTEGRITY_ERRORS = (sqlite3.IntegrityError,) + ((psycopg2.IntegrityError,) if psycopg2 else ())
ID_TABLES = {"users", "experiences", "posts", "comments", "jobs", "applications", "connections", "messages"}


@st.cache_resource
def _pg_pool(url):
    return psycopg2.pool.ThreadedConnectionPool(1, 10, dsn=url, connect_timeout=15)


def _pg_sql(sql):
    """Translate the (SQLite flavoured) SQL used by the app to Postgres."""
    out = sql.replace("%", "%%").replace("?", "%s")
    out = out.replace("CURRENT_TIMESTAMP", "(NOW() AT TIME ZONE 'UTC')")
    out = out.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    if re.match(r"\s*INSERT OR IGNORE INTO", out, re.I):
        out = re.sub(r"INSERT OR IGNORE INTO", "INSERT INTO", out, count=1, flags=re.I) + " ON CONFLICT DO NOTHING"
    m = re.match(r"\s*INSERT INTO\s+(\w+)", out, re.I)
    returning = bool(m and m.group(1).lower() in ID_TABLES and "RETURNING" not in out.upper())
    if returning:
        out += " RETURNING id"
    return out, returning


def _run_pg(sql, params, fetch):
    if psycopg2 is None:
        raise RuntimeError("DATABASE_URL is set but psycopg2 is not installed. Add psycopg2-binary to requirements.txt.")
    pool = _pg_pool(db_url())
    psql, returning = _pg_sql(sql)
    for attempt in (0, 1):
        conn = pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(psql, params)
                rows, last = None, None
                if returning:
                    r = cur.fetchone()
                    last = r["id"] if r else None
                elif fetch:
                    rows = []
                    for r in cur.fetchall():
                        rows.append({k: (v.strftime("%Y-%m-%d %H:%M:%S") if isinstance(v, datetime) else v)
                                     for k, v in r.items()})
            pool.putconn(conn)
            return rows, last
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            pool.putconn(conn, close=True)           # the server dropped an idle connection: retry once
            if attempt:
                raise
        except Exception:
            pool.putconn(conn)
            raise


def _run(sql, params=(), fetch=True):
    if db_url():
        return _run_pg(sql, params, fetch)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()] if fetch else None
        conn.commit()
        return rows, cur.lastrowid
    finally:
        conn.close()


def q(sql, params=()):
    return _run(sql, params)[0]


def q1(sql, params=()):
    rows = q(sql, params)
    return rows[0] if rows else None


def ex(sql, params=()):
    return _run(sql, params, fetch=False)[1]


@st.cache_resource
def init_db():
    if db_url():
        for stmt in SCHEMA.split(";"):
            if stmt.strip():
                ex(stmt)
        ex("ALTER TABLE posts ADD COLUMN IF NOT EXISTS video_path TEXT")
        return True
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    # migrate databases created by older versions of the app
    for table, wanted in [("seekers", [("headline", "TEXT"), ("photo_path", "TEXT"), ("open_to_work", "INTEGER DEFAULT 1")]),
                          ("posts", [("video_path", "TEXT")])]:
        cols = {r["name"] for r in q(f"PRAGMA table_info({table})")}
        for col, typ in wanted:
            if col not in cols:
                ex(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    # older versions kept files in uploads/; videos now live in static/ so the player can stream them
    old = Path("uploads")
    if old.is_dir():
        for f in old.iterdir():
            if f.is_file() and not (UPLOAD_DIR / f.name).exists():
                shutil.move(str(f), UPLOAD_DIR / f.name)
        for tbl, col in [("seekers", "video_path"), ("seekers", "photo_path"), ("companies", "photo_path"),
                         ("jobs", "video_path"), ("posts", "image_path")]:
            ex(f"UPDATE {tbl} SET {col} = 'static/' || SUBSTR({col}, 9) WHERE {col} LIKE 'uploads/%'")
    return True


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------
esc = html.escape


def safe(text):
    """Escape user text for use inside our own HTML."""
    return esc(text or "").replace("\n", "<br>")


def ago(ts):
    try:
        d = datetime.now(timezone.utc).replace(tzinfo=None) - datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""
    s = int(d.total_seconds())
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{s // 60}m ago"
    if s < 86400:
        return f"{s // 3600}h ago"
    return f"{s // 86400}d ago"


def hash_pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()


def create_user(role, name, email, salt, pw_hash):
    try:
        uid = ex("INSERT INTO users(role,name,email,salt,pw_hash) VALUES(?,?,?,?,?)",
                 (role, name.strip(), email.strip().lower(), salt, pw_hash))
        return uid, None
    except INTEGRITY_ERRORS:
        return None, "This email is already registered."


def register(role, name, email, password):
    salt = secrets.token_hex(8)
    return create_user(role, name, email, salt, hash_pw(password, salt))


# ----------------------------------------------------------------------------
# Email verification (6-digit code sent by SMTP)
# ----------------------------------------------------------------------------
CODE_TTL = 10 * 60        # a code is valid for 10 minutes
RESEND_WAIT = 60          # seconds between two codes for the same email
MAX_SENDS_PER_HOUR = 5
MAX_TRIES = 5             # wrong guesses allowed per code
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def _setting(key, default=None):
    """Read a setting from environment variables first, then .streamlit/secrets.toml."""
    v = os.environ.get(key)
    if v:
        return v
    try:
        v = st.secrets.get(key)
        if v in (None, ""):                      # also accept  [smtp]  host = "..."  style tables
            tbl = st.secrets.get("smtp") or st.secrets.get("SMTP") or {}
            v = tbl.get(key) or tbl.get(key.replace("SMTP_", "").lower())
        return v if v not in (None, "") else default
    except Exception:
        return default


def smtp_config():
    host, user, pw = _setting("SMTP_HOST"), _setting("SMTP_USER"), _setting("SMTP_PASSWORD")
    if not (host and user and pw):
        return None
    port = int(_setting("SMTP_PORT", 587))
    default_sec = "ssl" if port == 465 else "starttls"
    return dict(host=str(host).strip(), user=str(user).strip(), password=str(pw).replace(" ", ""),   # Gmail shows app passwords with spaces
                port=port, security=str(_setting("SMTP_SECURITY", default_sec)).lower(),   # starttls | ssl | none
                sender=_setting("SMTP_FROM") or str(user).strip())


def send_code_email(to, name, code, purpose="signup"):
    """Send the code. Returns (ok, error_message)."""
    c = smtp_config()
    if not c:
        return False, "Email is not configured on the server."
    msg = EmailMessage()
    reset = purpose == "reset"
    what = "reset your password" if reset else "finish signing up"
    msg["Subject"] = f"{code} is your JobTok {'password reset' if reset else 'verification'} code"
    msg["From"] = c["sender"]
    msg["To"] = to
    msg.set_content(f"Hi {name},\n\nYour JobTok verification code is: {code}\n\n"
                    f"Use it to {what}. It expires in {CODE_TTL // 60} minutes. "
                    f"If this wasn't you, ignore this email.\n")
    msg.add_alternative(f"""\
<div style="font-family:Arial,sans-serif;max-width:420px;margin:auto;padding:24px;background:#111;color:#fff;border-radius:16px">
  <h2 style="margin:0 0 4px">🎬 JobTok</h2>
  <p style="color:#aaa;margin:0 0 18px">Hi {html.escape(name)}, use this code to {what}.</p>
  <div style="font-size:36px;letter-spacing:10px;font-weight:800;text-align:center;padding:16px;
              background:#1d1d1d;border-radius:12px;color:#25f4ee">{code}</div>
  <p style="color:#aaa;font-size:13px;margin-top:18px">This code expires in {CODE_TTL // 60} minutes.
     If you didn't request it, you can ignore this email.</p>
</div>""", subtype="html")
    try:
        if c["security"] == "ssl":
            server = smtplib.SMTP_SSL(c["host"], c["port"], context=ssl.create_default_context(), timeout=20)
        else:
            server = smtplib.SMTP(c["host"], c["port"], timeout=20)
            if c["security"] == "starttls":
                server.starttls(context=ssl.create_default_context())
        with server:
            server.login(c["user"], c["password"])
            server.send_message(msg)
        return True, None
    except smtplib.SMTPAuthenticationError:
        print("[JobTok] SMTP login rejected - check SMTP_USER / SMTP_PASSWORD (Gmail needs an App Password)", flush=True)
        return False, ("The mail server rejected the login. Server owner: check SMTP_USER and SMTP_PASSWORD "
                       "(Gmail needs a 16-letter App Password, not the normal password).")
    except smtplib.SMTPRecipientsRefused:
        return False, "The mail server refused that email address. Please check it for typos."
    except smtplib.SMTPSenderRefused:
        print("[JobTok] SMTP sender refused - SMTP_FROM must be an address your provider allows", flush=True)
        return False, "The mail server refused the sender address (server owner: check SMTP_FROM)."
    except (ssl.SSLError, smtplib.SMTPNotSupportedError, smtplib.SMTPServerDisconnected) as e:
        print(f"[JobTok] SMTP security mismatch: {e!r}", flush=True)
        return False, ("Could not open a secure connection (server owner: use SMTP_PORT=587 with "
                       "SMTP_SECURITY=starttls, or SMTP_PORT=465 with SMTP_SECURITY=ssl).")
    except OSError as e:                        # DNS failure, refused, timeout, blocked port
        print(f"[JobTok] SMTP cannot connect to {c['host']}:{c['port']}: {e!r}", flush=True)
        return False, (f"Could not reach the mail server {c['host']}:{c['port']} (server owner: check SMTP_HOST / "
                       "SMTP_PORT - many hosts block these ports, try 465 or 2525).")
    except Exception as e:
        print(f"[JobTok] SMTP error: {e!r}", flush=True)
        return False, f"Could not send the email ({type(e).__name__}). Please try again."


def _code_hash(salt, code):
    return hashlib.sha256(f"{salt}:{code}".encode()).hexdigest()


def issue_code(email):
    """Create a fresh code for this email. Returns (code, error)."""
    now = time.time()
    row = q1("SELECT * FROM email_codes WHERE email=?", (email,))
    sends, window = 1, now
    if row:
        wait = RESEND_WAIT - (now - (row["last_sent"] or 0))
        if wait > 0:
            return None, f"Please wait {int(wait) + 1} seconds before asking for another code."
        if now - (row["window_start"] or 0) < 3600:
            if (row["sends"] or 0) >= MAX_SENDS_PER_HOUR:
                return None, "Too many codes requested for this email. Please try again in an hour."
            sends, window = (row["sends"] or 0) + 1, row["window_start"]
    code = f"{secrets.randbelow(10 ** 6):06d}"
    salt = secrets.token_hex(8)
    ex("""INSERT INTO email_codes(email,salt,code_hash,expires,attempts,last_sent,window_start,sends)
          VALUES(?,?,?,?,0,?,?,?)
          ON CONFLICT(email) DO UPDATE SET salt=excluded.salt, code_hash=excluded.code_hash,
            expires=excluded.expires, attempts=0, last_sent=excluded.last_sent,
            window_start=excluded.window_start, sends=excluded.sends""",
       (email, salt, _code_hash(salt, code), now + CODE_TTL, now, window, sends))
    return code, None


def check_code(email, code):
    """Returns (ok, error)."""
    row = q1("SELECT * FROM email_codes WHERE email=?", (email,))
    if not row or not row["code_hash"]:
        return False, "No code found. Please request a new one."
    if time.time() > (row["expires"] or 0):
        return False, "This code has expired. Please request a new one."
    if (row["attempts"] or 0) >= MAX_TRIES:
        return False, "Too many wrong attempts. Please request a new code."
    if not hmac.compare_digest(_code_hash(row["salt"], code.strip()), row["code_hash"]):
        ex("UPDATE email_codes SET attempts=attempts+1 WHERE email=?", (email,))
        left = MAX_TRIES - (row["attempts"] or 0) - 1
        return False, "Wrong code." + (f" {left} tries left." if left > 0 else " Please request a new code.")
    ex("UPDATE email_codes SET code_hash=NULL, expires=0 WHERE email=?", (email,))   # one use only
    return True, None


def login(email, password):
    row = q1("SELECT * FROM users WHERE email=?", (email.strip().lower(),))
    if row and hash_pw(password, row["salt"]) == row["pw_hash"]:
        return row
    return None


# ---------- stay logged in until the user logs out ----------
COOKIE = "jobtok_login"
LOGIN_DAYS = 365 * 5                      # server side; the user stays in until they press Log out


def _tok_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def remember_login(uid):
    """Create a login token; it is sent to the browser (cookie) on the next page draw."""
    token = secrets.token_urlsafe(32)
    now = time.time()
    ex("DELETE FROM sessions WHERE expires<?", (now,))
    ex("INSERT INTO sessions(token_hash, user_id, created, expires) VALUES(?,?,?,?)",
       (_tok_hash(token), uid, now, now + LOGIN_DAYS * 86400))
    st.session_state["_cookie_set"] = token


def restore_login():
    """New visit / refresh / app reopened: log the user in again from the saved cookie."""
    try:
        token = st.context.cookies.get(COOKIE)
    except Exception:
        return None
    if not token or not isinstance(token, str):
        return None
    row = q1("SELECT s.user_id, s.expires, u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?",
             (_tok_hash(token),))
    if not row or row["expires"] < time.time():
        return None
    st.session_state["_cookie_set"] = token              # refresh the cookie lifetime
    ex("UPDATE sessions SET expires=? WHERE token_hash=?", (time.time() + LOGIN_DAYS * 86400, _tok_hash(token)))
    return {"id": row["user_id"], "role": row["role"], "name": row["name"], "email": row["email"]}


def forget_login(uid=None, everywhere=False):
    """Log out: remove this browser's token (or every token of the user)."""
    if everywhere and uid:
        ex("DELETE FROM sessions WHERE user_id=?", (uid,))
        return
    try:
        token = st.context.cookies.get(COOKIE)
    except Exception:
        token = None
    if token and isinstance(token, str):
        ex("DELETE FROM sessions WHERE token_hash=?", (_tok_hash(token),))


def sync_cookie():
    """Write or clear the browser cookie when a login/logout just happened."""
    token = st.session_state.pop("_cookie_set", None)
    clear = st.session_state.pop("_cookie_clear", False) if token is None else False
    if token is None and not clear:
        return
    val, age = (token, 400 * 86400) if token else ("", 0)
    js = ("<script>try{var h=window.parent.location.protocol==='https:'?';Secure':'';"
          f"window.parent.document.cookie='{COOKIE}={val};max-age={age};path=/;SameSite=Lax'+h;"
          "}catch(e){}</script>")
    if hasattr(st, "iframe"):
        st.iframe(js, height=1)
    else:
        components.html(js, height=0)


def do_logout(me=None):
    forget_login()
    st.session_state.clear()
    st.session_state["_cookie_clear"] = True
    st.rerun()


def video_duration(path: str):
    try:
        import cv2

        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        cap.release()
        if fps > 0 and frames > 0:
            return frames / fps
    except Exception:
        pass
    return None


# ---- permanent file storage (Supabase Storage). Without SUPABASE_URL the files stay in ./static (temporary on cloud hosts)
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB") or 50)          # Supabase free plan allows 50 MB per file
MIME = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm", ".m4v": "video/x-m4v", ".jpg": "image/jpeg"}


def storage_conf():
    url, key = _setting("SUPABASE_URL"), _setting("SUPABASE_SERVICE_KEY")
    if not (url and key):
        return None
    return dict(url=str(url).strip().rstrip("/"), key=str(key).strip(), bucket=_setting("SUPABASE_BUCKET", "jobtok"))


def is_url(path):
    return isinstance(path, str) and path.startswith(("http://", "https://"))


@st.cache_resource
def _ensure_bucket(url, key, bucket):
    import requests

    try:                                   # creates a PUBLIC bucket; an error just means it already exists
        requests.post(f"{url}/storage/v1/bucket", timeout=20, json={"id": bucket, "name": bucket, "public": True},
                      headers={"Authorization": f"Bearer {key}", "apikey": key})
    except Exception:
        pass
    return True


def store_file(local_path, content_type):
    """Move a finished local file to permanent storage. Returns the public URL (or the local path if not configured)."""
    c = storage_conf()
    local_path = Path(local_path)
    if not c:
        return str(local_path)
    import requests

    _ensure_bucket(c["url"], c["key"], c["bucket"])
    with open(local_path, "rb") as f:
        r = requests.post(f"{c['url']}/storage/v1/object/{c['bucket']}/{local_path.name}", data=f, timeout=600,
                          headers={"Authorization": f"Bearer {c['key']}", "apikey": c["key"],
                                   "Content-Type": content_type, "x-upsert": "true"})
    if r.status_code >= 300:
        raise RuntimeError(f"storage upload failed ({r.status_code}): {r.text[:200]}")
    local_path.unlink(missing_ok=True)
    return f"{c['url']}/storage/v1/object/public/{c['bucket']}/{local_path.name}"


def save_video(uploaded):
    """Validate (size, <= 30 s) and store the video. Returns (path_or_url, error)."""
    if uploaded.size > MAX_UPLOAD_MB * 1024 * 1024:
        return None, f"This video is {uploaded.size / 1048576:.0f} MB. Please keep it under {MAX_UPLOAD_MB} MB."
    suffix = Path(uploaded.name).suffix.lower() or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getbuffer())
        tmp_path = Path(tmp.name)
    dur = video_duration(str(tmp_path))
    if dur is not None and dur > MAX_SECONDS + 0.5:
        tmp_path.unlink(missing_ok=True)
        return None, f"Your video is {dur:.0f} seconds long. Please keep it to {MAX_SECONDS} seconds or less."
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    shutil.move(str(tmp_path), dest)
    try:
        return store_file(dest, MIME.get(suffix, "video/mp4")), None
    except Exception as e:
        dest.unlink(missing_ok=True)
        print(f"[JobTok] {e}", flush=True)
        return None, "Could not save the video to storage. Please try again in a moment."


def save_image(uploaded, size=None, max_side=1080):
    """Resize + store an image as JPEG. Returns (path_or_url, error)."""
    try:
        from PIL import Image, ImageOps

        img = ImageOps.exif_transpose(Image.open(uploaded)).convert("RGB")
        if size:
            img = ImageOps.fit(img, size)
        else:
            img.thumbnail((max_side, max_side))
        dest = UPLOAD_DIR / f"{uuid.uuid4().hex}.jpg"
        img.save(dest, "JPEG", quality=85)
    except Exception:
        return None, "Could not read that image. Please use a JPG or PNG."
    try:
        return store_file(dest, "image/jpeg"), None
    except Exception as e:
        dest.unlink(missing_ok=True)
        print(f"[JobTok] {e}", flush=True)
        return None, "Could not save the image to storage. Please try again in a moment."


def drop_file(path):
    """Delete an old file (local file, or an object in our storage bucket)."""
    if not path:
        return
    if is_url(path):
        c = storage_conf()
        prefix = f"{c['url']}/storage/v1/object/public/{c['bucket']}/" if c else None
        if c and path.startswith(prefix):
            try:
                import requests

                requests.delete(f"{c['url']}/storage/v1/object/{c['bucket']}/{path[len(prefix):]}", timeout=20,
                                headers={"Authorization": f"Bearer {c['key']}", "apikey": c["key"]})
            except Exception:
                pass
        return
    Path(path).unlink(missing_ok=True)


def exists(path):
    return bool(path) and (is_url(path) or Path(path).exists())


# ----------------------------------------------------------------------------
# People
# ----------------------------------------------------------------------------
def get_person(uid):
    u = q1("SELECT id, role, name, email FROM users WHERE id=?", (uid,))
    if not u:
        return None
    table = "seekers" if u["role"] == "seeker" else "companies"
    p = q1(f"SELECT * FROM {table} WHERE user_id=?", (uid,)) or {}
    return {**p, **u}


def headline_of(p):
    if p["role"] == "seeker":
        return p.get("headline") or p.get("title") or "Job seeker"
    return " • ".join(x for x in [p.get("industry"), p.get("size") and f"{p['size']} employees"] if x) or "Company"


@st.cache_data(show_spinner=False)
def _b64(path, mtime):
    return base64.b64encode(Path(path).read_bytes()).decode()


def avatar_html(p, size=48):
    path = p.get("photo_path")
    if exists(path) and is_url(path):
        return (f'<img src="{esc(path)}" loading="lazy" '
                f'style="width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;flex:none">')
    if exists(path):
        data = _b64(path, Path(path).stat().st_mtime)
        return (f'<img src="data:image/jpeg;base64,{data}" '
                f'style="width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;flex:none">')
    ini = esc((p.get("name") or "?")[:1].upper())
    return f'<div class="av" style="width:{size}px;height:{size}px;font-size:{size // 2}px">{ini}</div>'


def person_header(p, size=48, extra=""):
    badge = ""
    if p["role"] == "seeker" and p.get("open_to_work"):
        badge = '<span class="badge">Open to work</span>'
    elif p["role"] == "company":
        badge = '<span class="badge co">Company</span>'
    st.markdown(
        f'<div class="phead">{avatar_html(p, size)}<div>'
        f'<div class="name">{esc(p["name"])}{badge}</div>'
        f'<div class="sub">{esc(headline_of(p))}</div>'
        f'<div class="meta">{extra}</div></div></div>',
        unsafe_allow_html=True,
    )


def chips(text, n=8, first=""):
    items = [s.strip() for s in (text or "").split(",") if s.strip()][:n]
    return (f'<span class="chip hot">{esc(first)}</span>' if first else "") + \
        "".join(f'<span class="chip">{esc(s)}</span>' for s in items)


# ----------------------------------------------------------------------------
# Video player with automatic text overlay (salary, experience, education ...)
# ----------------------------------------------------------------------------
def person_overlay(p):
    items = []
    if p.get("experience") is not None:
        items.append(f"💼 {p['experience']} yrs experience")
    if p.get("education"):
        items.append(f"🎓 {p['education']}")
    if p.get("salary"):
        items.append(f"💰 {p['salary']:,} / month expected")
    if p.get("city"):
        items.append(f"📍 {p['city']}")
    skills = [s.strip() for s in (p.get("skills") or "").split(",") if s.strip()][:4]
    if skills:
        items.append("🛠 " + " · ".join(skills))
    return dict(title=p["name"], subtitle=p.get("title") or headline_of(p), items=items,
                badge="Open to work" if p.get("open_to_work") else "")


def job_overlay(j, company_name=""):
    items = []
    if j.get("salary_min") or j.get("salary_max"):
        items.append(f"💰 {(j.get('salary_min') or 0):,} – {(j.get('salary_max') or 0):,} / month")
    items.append(f"📍 {j.get('city') or '-'} · {j.get('job_type') or ''}")
    skills = [s.strip() for s in (j.get("skills") or "").split(",") if s.strip()][:4]
    if skills:
        items.append("🛠 " + " · ".join(skills))
    if j.get("category"):
        items.append(f"🏷 {j['category']}")
    return dict(title=j["title"], subtitle=company_name, items=items, badge="Hiring")


VIDEO_RATIO = "4 / 5"      # every video uses the SAME box: 4 wide x 5 tall (cropped to fill, no black bars)
VIDEO_MAX_W = 420          # px - the box never gets wider than this


def video_player(path, title="", subtitle="", items=(), badge=""):
    """One uniform video box: autoplays muted when on screen, closes (pause + reset + unload) when scrolled away,
    only one plays at a time, and info lines fade in over the video one by one."""
    if not exists(path):
        return
    if is_url(path):
        url = path
    else:
        p = Path(path)
        if not (st.get_option("server.enableStaticServing") and p.parent.name == UPLOAD_DIR.name):
            st.video(path)                       # static serving is off: plain player + info as a caption
            if items:
                st.caption("  •  ".join(items))
            return
        url = f"/app/static/{quote(p.name)}"
    pills = "".join(f'<div class="pill">{esc(t)}</div>' for t in items)
    badge_html = f'<span class="bdg">{esc(badge)}</span>' if badge else ""
    doc = f"""
<style>
  html,body{{margin:0;background:transparent;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
  .w{{position:relative;width:100%;max-width:{VIDEO_MAX_W}px;margin:0 auto;aspect-ratio:{VIDEO_RATIO};border-radius:18px;
     overflow:hidden;background:#111}}
  video{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;background:#111}}
  .top{{position:absolute;left:0;right:0;top:0;padding:14px 16px 28px;color:#fff;pointer-events:none;
       background:linear-gradient(180deg,rgba(0,0,0,.75),rgba(0,0,0,0))}}
  .top b{{font-size:19px;text-shadow:0 1px 4px #000}}
  .top small{{display:block;color:#25f4ee;font-weight:700;font-size:13px;margin-top:2px;text-shadow:0 1px 4px #000}}
  .bdg{{background:#0a7d3c;border-radius:10px;padding:2px 9px;margin-left:8px;font-size:11px;font-weight:700;vertical-align:middle}}
  .ov{{position:absolute;left:12px;right:84px;bottom:58px;display:flex;flex-direction:column;gap:7px;pointer-events:none}}
  .pill{{align-self:flex-start;background:rgba(0,0,0,.62);backdrop-filter:blur(6px);color:#fff;padding:7px 13px;
        border-radius:20px;font-size:14px;font-weight:600;border-left:4px solid #fe2c55;
        opacity:0;transform:translateY(16px);transition:opacity .55s ease,transform .55s ease;max-width:100%}}
  .pill.on{{opacity:1;transform:none}}
  @media (max-width:420px){{.pill{{font-size:12.5px;padding:5px 10px}}.top b{{font-size:16px}}.ov{{right:68px;bottom:50px}}}}
  .mute{{position:absolute;right:12px;top:12px;width:38px;height:38px;border-radius:50%;border:0;cursor:pointer;
        background:rgba(0,0,0,.55);color:#fff;font-size:18px}}
</style>
<div class="w" id="box">
  <video id="v" data-src="{esc(url)}" muted loop playsinline preload="metadata" controls controlsList="nodownload"></video>
  <div class="top"><b>{esc(title)}</b>{badge_html}<small>{esc(subtitle)}</small></div>
  <div class="ov">{pills}</div>
  <button class="mute" id="m" title="Sound on/off">🔇</button>
</div>
<script>
  const v=document.getElementById('v'), m=document.getElementById('m'), box=document.getElementById('box');
  const SRC=v.dataset.src, pills=[...document.querySelectorAll('.pill')];
  const ME=Math.random().toString(36).slice(2);
  const ch=('BroadcastChannel' in window)?new BroadcastChannel('jobtok-video'):null;
  function pillsOff(){{pills.forEach(p=>p.classList.remove('on'));}}
  function load(){{ if(v.getAttribute('src')!==SRC) v.src=SRC; }}
  function closeIt(){{ v.pause(); try{{v.currentTime=0;}}catch(e){{}} pillsOff(); }}      // scrolled away: stop + rewind
  function unload(){{ v.pause(); if(v.getAttribute('src')){{ v.removeAttribute('src'); v.load(); }} pillsOff(); }}  // far away: free memory
  function update(){{
    const dur=(isFinite(v.duration)&&v.duration>4)?v.duration:30;
    const step=Math.min(2.2,(dur-1.5)/(pills.length+1));
    pills.forEach((p,i)=>p.classList.toggle('on', v.currentTime>=0.7+i*step));
  }}
  v.addEventListener('timeupdate',update); v.addEventListener('seeked',update); v.addEventListener('loadedmetadata',update);
  v.addEventListener('play',()=>{{ if(ch) ch.postMessage(ME); }});                         // tell the other videos to stop
  if(ch) ch.onmessage=e=>{{ if(e.data!==ME && !v.paused) v.pause(); }};
  m.onclick=()=>{{v.muted=!v.muted; m.textContent=v.muted?'🔇':'🔊';}};
  new IntersectionObserver(es=>es.forEach(e=>{{
      if(e.intersectionRatio>=0.6){{ load(); v.play().catch(()=>{{}}); }}
      else if(e.intersectionRatio<0.25){{ closeIt(); }}
  }}),{{threshold:[0,0.25,0.6]}}).observe(box);
  new IntersectionObserver(es=>es.forEach(e=>{{ if(e.isIntersecting) load(); else unload(); }}),
      {{rootMargin:'900px 0px 900px 0px'}}).observe(box);
</script>"""
    if hasattr(st, "iframe"):          # st.components.v1.html is deprecated in newer Streamlit
        st.iframe(doc, height="content")
    else:
        components.html(doc, height=int(VIDEO_MAX_W * 5 / 4) + 4)


def show_person_video(p):
    if exists(p.get("video_path")):
        video_player(p["video_path"], **person_overlay(p))


# ----------------------------------------------------------------------------
# CV download (PDF generated from the profile)
# ----------------------------------------------------------------------------
_DL = {"on_click": "ignore"} if tuple(int(x) for x in st.__version__.split(".")[:2]) >= (1, 43) else {}


def contact_visible(me, role, uid):
    """Email/phone are shared only with the owner, connections, and companies the person applied to / shortlisted."""
    if me == uid or conn_status(me, uid) == "connected":
        return True
    if role == "company":
        if uid in shortlisted_ids(me):
            return True
        return q1("""SELECT 1 x FROM applications a JOIN jobs j ON j.id=a.job_id
                     WHERE j.company_id=? AND a.seeker_id=?""", (me, uid)) is not None
    return False


def _pdf_font(pdf):
    """Use a Unicode TTF if the machine has one, otherwise the built-in Helvetica (Latin only)."""
    pairs = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ("/Library/Fonts/Arial Unicode.ttf", None),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ]
    for reg, bold in pairs:
        if Path(reg).exists():
            pdf.add_font("CV", "", reg)
            pdf.add_font("CV", "B", bold if bold and Path(bold).exists() else reg)
            return "CV", True
    return "Helvetica", False


@st.cache_data(show_spinner=False)
def _cv_pdf(uid, stamp, show_contact):
    from fpdf import FPDF

    p = get_person(uid)
    exps = q("SELECT * FROM experiences WHERE user_id=? ORDER BY id DESC", (uid,))
    pdf = FPDF()
    pdf.set_auto_page_break(True, 15)
    pdf.add_page()
    fam, uni = _pdf_font(pdf)

    def T(x):
        x = str(x or "")
        return x if uni else x.encode("latin-1", "replace").decode("latin-1")

    # header band
    pdf.set_fill_color(18, 18, 18)
    pdf.rect(0, 0, 210, 44, "F")
    if exists(p.get("photo_path")):
        try:
            pdf.image(p["photo_path"], x=170, y=8, w=28, h=28)
        except Exception:
            pass
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(fam, "B", 22)
    pdf.set_xy(15, 9)
    pdf.cell(150, 10, T(p["name"]))
    pdf.set_font(fam, "", 12)
    pdf.set_text_color(37, 244, 238)
    pdf.set_xy(15, 21)
    pdf.cell(150, 7, T(p.get("title") or headline_of(p)))
    pdf.set_font(fam, "", 9.5)
    pdf.set_text_color(200, 200, 200)
    pdf.set_xy(15, 31)
    if show_contact:
        line = " | ".join(x for x in [p.get("email"), p.get("phone"), p.get("city")] if x)
    else:
        line = " | ".join(x for x in [p.get("city"), "Contact via JobTok chat"] if x)
    pdf.cell(150, 6, T(line))
    pdf.set_y(52)

    def section(title):
        pdf.ln(3)
        pdf.set_font(fam, "B", 12)
        pdf.set_text_color(254, 44, 85)
        pdf.cell(0, 8, T(title.upper()), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(220, 220, 220)
        pdf.line(pdf.l_margin, pdf.get_y(), 210 - pdf.r_margin, pdf.get_y())
        pdf.ln(2)
        pdf.set_text_color(30, 30, 30)

    def body(text, size=10.5, bold=False):
        pdf.set_font(fam, "B" if bold else "", size)
        pdf.multi_cell(0, 5.6, T(text), new_x="LMARGIN", new_y="NEXT")

    if p.get("headline"):
        pdf.set_text_color(60, 60, 60)
        body(p["headline"], 11)
    section("Key details")
    details = [("Experience", f"{p.get('experience') or 0} years"), ("Category", p.get("category")),
               ("Expected salary", f"{(p.get('salary') or 0):,} per month" if p.get("salary") else None),
               ("Location", p.get("city")), ("Education", p.get("education")),
               ("Status", "Open to work" if p.get("open_to_work") else None)]
    for k, v in details:
        if v:
            pdf.set_font(fam, "B", 10.5)
            pdf.cell(40, 6, T(k + ":"))
            pdf.set_font(fam, "", 10.5)
            pdf.multi_cell(0, 6, T(v), new_x="LMARGIN", new_y="NEXT")
    if p.get("about"):
        section("About")
        body(p["about"])
    if p.get("skills"):
        section("Skills")
        body(", ".join(s.strip() for s in p["skills"].split(",") if s.strip()))
    if exps:
        section("Experience")
        for e in exps:
            body(f"{e['role']} - {e['company'] or ''}", 11, bold=True)
            pdf.set_text_color(110, 110, 110)
            body(f"{e['start'] or ''} - {e['end'] or 'Present'}", 9.5)
            pdf.set_text_color(30, 30, 30)
            if e.get("description"):
                body(e["description"])
            pdf.ln(2)
    pdf.set_y(-18)
    pdf.set_font(fam, "", 8)
    pdf.set_text_color(140, 140, 140)
    pdf.cell(0, 5, T(f"Generated from the JobTok profile on {datetime.now().strftime('%d %b %Y')}"), align="C")
    return bytes(pdf.output())


def cv_button(me, role, p, key, label="📄 Download CV", help=None):
    """Download the job seeker's CV (PDF). Contact details are included only when allowed."""
    if not p or p["role"] != "seeker":
        return
    uid = p["id"]
    meta = q1("SELECT COUNT(*) n, COALESCE(MAX(id),0) m FROM experiences WHERE user_id=?", (uid,))
    stamp = f"{p.get('updated')}|{meta['n']}|{meta['m']}"
    try:
        data = _cv_pdf(uid, stamp, contact_visible(me, role, uid))
    except Exception:
        st.caption("CV unavailable")
        return
    safe_name = "".join(ch for ch in p["name"] if ch.isalnum() or ch in " _-").strip().replace(" ", "_") or "candidate"
    st.download_button(label, data=data, file_name=f"CV_{safe_name}.pdf", mime="application/pdf",
                       key=key, help=help or f"Download {p['name']}'s CV", **_DL)


@st.cache_data(show_spinner=False)
def _job_pdf(job_id, stamp):
    from fpdf import FPDF

    j = q1("SELECT * FROM jobs WHERE id=?", (job_id,))
    co = get_person(j["company_id"]) or {}
    pdf = FPDF()
    pdf.set_auto_page_break(True, 15)
    pdf.add_page()
    fam, uni = _pdf_font(pdf)

    def T(x):
        x = str(x or "")
        return x if uni else x.encode("latin-1", "replace").decode("latin-1")

    pdf.set_fill_color(18, 18, 18)
    pdf.rect(0, 0, 210, 40, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(fam, "B", 21)
    pdf.set_xy(15, 10)
    pdf.cell(180, 10, T(j["title"]))
    pdf.set_font(fam, "", 12)
    pdf.set_text_color(37, 244, 238)
    pdf.set_xy(15, 23)
    pdf.cell(180, 7, T(co.get("name")))
    pdf.set_y(50)
    pdf.set_text_color(30, 30, 30)
    sal = f"{(j['salary_min'] or 0):,} - {(j['salary_max'] or 0):,} per month" if (j["salary_min"] or j["salary_max"]) else None
    for k, v in [("Job type", j["job_type"]), ("Category", j["category"]), ("Location", j["city"]),
                 ("Salary", sal), ("Skills", j["skills"]), ("Posted", (j["created"] or "")[:10])]:
        if v:
            pdf.set_font(fam, "B", 10.5)
            pdf.cell(32, 6.5, T(k + ":"))
            pdf.set_font(fam, "", 10.5)
            pdf.multi_cell(0, 6.5, T(v), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font(fam, "B", 12)
    pdf.set_text_color(254, 44, 85)
    pdf.cell(0, 8, "DESCRIPTION", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(30, 30, 30)
    pdf.set_font(fam, "", 10.5)
    pdf.multi_cell(0, 5.6, T(j["description"]), new_x="LMARGIN", new_y="NEXT")
    if co.get("about"):
        pdf.ln(4)
        pdf.set_font(fam, "B", 12)
        pdf.set_text_color(254, 44, 85)
        pdf.cell(0, 8, "ABOUT THE COMPANY", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(30, 30, 30)
        pdf.set_font(fam, "", 10.5)
        pdf.multi_cell(0, 5.6, T(co["about"]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(-18)
    pdf.set_font(fam, "", 8)
    pdf.set_text_color(140, 140, 140)
    pdf.cell(0, 5, T("Apply and chat with the company on JobTok"), align="C")
    return bytes(pdf.output())


def job_download_button(j, key):
    try:
        data = _job_pdf(j["id"], f"{j['title']}|{j['description']}|{j['salary_min']}|{j['salary_max']}|{j['city']}")
    except Exception:
        return
    name = "".join(ch for ch in j["title"] if ch.isalnum() or ch in " _-").strip().replace(" ", "_") or "job"
    st.download_button("📄 Download job details", data=data, file_name=f"Job_{name}.pdf",
                       mime="application/pdf", key=key, **_DL)


def person_video_block(me, role, p, ctx):
    """Video with a TikTok-style action rail on its right edge: chat, like, CV, profile."""
    uid = p["id"]
    with st.container(key=f"vc_{ctx}_{uid}"):
        show_person_video(p)
        if uid != me and exists(p.get("video_path")):
            with st.container(key=f"rail_{ctx}_{uid}"):
                if st.button("✉️", key=f"rc_{ctx}_{uid}", help=f"Chat with {p['name']}"):
                    goto("messages", chat_with=uid)
                like_btn("video", uid, me, f"lk_{ctx}_{uid}")
                cv_button(me, role, p, f"rcv_{ctx}_{uid}", label="📄", help=f"Download {p['name']}'s CV")
                if st.button("👤", key=f"rp_{ctx}_{uid}", help="View full profile"):
                    open_profile(uid)


def job_video_block(me, j, co, ctx):
    with st.container(key=f"vc_{ctx}_j{j['id']}"):
        video_player(j["video_path"], **job_overlay(j, co["name"] if co else ""))
        if j["company_id"] != me:
            with st.container(key=f"rail_{ctx}_j{j['id']}"):
                if st.button("✉️", key=f"jrc_{ctx}_{j['id']}", help="Chat with the company"):
                    goto("messages", chat_with=j["company_id"])
                like_btn("job", j["id"], me, f"jl_{ctx}_{j['id']}")
                if st.button("🏢", key=f"jrp_{ctx}_{j['id']}", help="View company page"):
                    open_profile(j["company_id"])


# ----------------------------------------------------------------------------
# Navigation helpers
# ----------------------------------------------------------------------------
def goto(page, **state):
    st.session_state.nav_to = page
    st.session_state.view_uid = None
    for k, v in state.items():
        st.session_state[k] = v
    st.rerun()


def open_profile(uid):
    st.session_state.view_uid = uid
    st.rerun()


# ----------------------------------------------------------------------------
# Social building blocks: likes, comments, connections
# ----------------------------------------------------------------------------
def like_btn(kind, tid, me, key):
    n = q1("SELECT COUNT(*) n FROM likes WHERE kind=? AND target_id=?", (kind, tid))["n"]
    liked = q1("SELECT 1 x FROM likes WHERE kind=? AND target_id=? AND user_id=?", (kind, tid, me)) is not None
    if st.button(f"{'❤️' if liked else '🤍'} {n}", key=key):
        if liked:
            ex("DELETE FROM likes WHERE kind=? AND target_id=? AND user_id=?", (kind, tid, me))
        else:
            ex("INSERT OR IGNORE INTO likes(kind,target_id,user_id) VALUES(?,?,?)", (kind, tid, me))
        st.rerun()


def comments_block(kind, tid, me, ctx):
    cs = q("SELECT c.*, u.name FROM comments c JOIN users u ON u.id=c.user_id "
           "WHERE c.kind=? AND c.target_id=? ORDER BY c.id", (kind, tid))
    with st.expander(f"💬 Comments ({len(cs)})"):
        for c in cs[-20:]:
            st.markdown(f'<div class="meta"><b>{esc(c["name"])}</b> · {ago(c["created"])}</div>'
                        f'<div class="body">{safe(c["body"])}</div>', unsafe_allow_html=True)
        with st.form(f"cf_{ctx}_{kind}_{tid}", clear_on_submit=True):
            body = st.text_input("Comment", placeholder="Add a comment…", label_visibility="collapsed",
                                 max_chars=300)
            if st.form_submit_button("Send"):
                if body.strip():
                    ex("INSERT INTO comments(kind,target_id,user_id,body) VALUES(?,?,?,?)",
                       (kind, tid, me, body.strip()))
                    st.rerun()


def conn_status(me, other):
    if me == other:
        return "self"
    r = q1("SELECT * FROM connections WHERE (from_id=? AND to_id=?) OR (from_id=? AND to_id=?)",
           (me, other, other, me))
    if not r:
        return "none"
    if r["status"] == "accepted":
        return "connected"
    return "sent" if r["from_id"] == me else "received"


def connect_btn(me, other, key):
    s = conn_status(me, other)
    if s == "self":
        return
    if s == "none":
        if st.button("🤝 Connect", key=key):
            ex("INSERT OR IGNORE INTO connections(from_id,to_id,status) VALUES(?,?,'pending')", (me, other))
            st.rerun()
    elif s == "sent":
        st.button("⏳ Pending", key=key, disabled=True)
    elif s == "received":
        if st.button("✅ Accept", key=key):
            ex("UPDATE connections SET status='accepted' WHERE from_id=? AND to_id=?", (other, me))
            st.rerun()
    else:
        st.button("✓ Connected", key=key, disabled=True)


def my_connection_ids(me):
    rows = q("SELECT from_id, to_id FROM connections WHERE status='accepted' AND (from_id=? OR to_id=?)", (me, me))
    return [r["to_id"] if r["from_id"] == me else r["from_id"] for r in rows]


def shortlisted_ids(company_id):
    return {r["seeker_id"] for r in q("SELECT seeker_id FROM shortlist WHERE company_id=?", (company_id,))}


def toggle_shortlist(company_id, seeker_id):
    if q1("SELECT 1 x FROM shortlist WHERE company_id=? AND seeker_id=?", (company_id, seeker_id)):
        ex("DELETE FROM shortlist WHERE company_id=? AND seeker_id=?", (company_id, seeker_id))
    else:
        ex("INSERT OR IGNORE INTO shortlist(company_id,seeker_id) VALUES(?,?)", (company_id, seeker_id))


# ----------------------------------------------------------------------------
# Search
# ----------------------------------------------------------------------------
def search_candidates(f):
    sql = """SELECT s.*, u.name FROM seekers s JOIN users u ON u.id=s.user_id
             WHERE s.video_path IS NOT NULL AND s.video_path != ''"""
    params = []
    if f["category"] != "All":
        sql += " AND s.category=?"
        params.append(f["category"])
    if f["city"].strip():
        sql += " AND LOWER(s.city) LIKE ?"
        params.append(f"%{f['city'].strip().lower()}%")
    sql += " AND s.experience >= ? AND s.experience <= ?"
    params += [f["exp"][0], f["exp"][1]]
    if f["max_salary"] > 0:
        sql += " AND s.salary <= ?"
        params.append(f["max_salary"])
    if f.get("open_only"):
        sql += " AND s.open_to_work=1"
    for kw in [k.strip().lower() for k in f["keywords"].replace(",", " ").split() if k.strip()]:
        sql += (" AND LOWER(COALESCE(u.name,'')||' '||COALESCE(s.headline,'')||' '||COALESCE(s.title,'')||' '||"
                "COALESCE(s.skills,'')||' '||COALESCE(s.about,'')||' '||COALESCE(s.education,'')) LIKE ?")
        params.append(f"%{kw}%")
    sql += " ORDER BY s.updated DESC"
    return q(sql, params)


def people_filters(prefix):
    with st.expander("🔎 Filters"):
        kw = st.text_input("Keywords (name, skill, title)", key=f"{prefix}_kw", placeholder="python, designer, react")
        c1, c2 = st.columns(2)
        cat = c1.selectbox("Category", ["All"] + CATEGORIES, key=f"{prefix}_cat")
        city = c2.text_input("City", key=f"{prefix}_city")
        exp = st.slider("Experience (years)", 0, 30, (0, 30), key=f"{prefix}_exp")
        c3, c4 = st.columns(2)
        sal = c3.number_input("Max salary / month (0 = any)", 0, 10_000_000, 0, step=5000, key=f"{prefix}_sal")
        open_only = c4.checkbox("Open to work only", key=f"{prefix}_open")
    return dict(keywords=kw, category=cat, city=city, exp=exp, max_salary=int(sal), open_only=open_only)


def search_jobs(f, company_id=None):
    sql = """SELECT j.*, u.name AS company_name FROM jobs j JOIN users u ON u.id=j.company_id WHERE j.active=1"""
    params = []
    if company_id:
        sql += " AND j.company_id=?"
        params.append(company_id)
    if f.get("category", "All") != "All":
        sql += " AND j.category=?"
        params.append(f["category"])
    if f.get("job_type", "All") != "All":
        sql += " AND j.job_type=?"
        params.append(f["job_type"])
    if f.get("city", "").strip():
        sql += " AND LOWER(j.city) LIKE ?"
        params.append(f"%{f['city'].strip().lower()}%")
    if f.get("min_salary", 0) > 0:
        sql += " AND j.salary_max >= ?"
        params.append(f["min_salary"])
    if f.get("video_only"):
        sql += " AND j.video_path IS NOT NULL AND j.video_path != ''"
    for kw in [k.strip().lower() for k in f.get("keywords", "").replace(",", " ").split() if k.strip()]:
        sql += (" AND LOWER(COALESCE(j.title,'')||' '||COALESCE(j.skills,'')||' '||COALESCE(j.description,'')||"
                "' '||COALESCE(u.name,'')) LIKE ?")
        params.append(f"%{kw}%")
    sql += " ORDER BY j.id DESC"
    return q(sql, params)


def job_filters(prefix, video_only=False):
    with st.expander("🔎 Filters"):
        kw = st.text_input("Keywords (title, skill, company)", key=f"{prefix}_kw")
        c1, c2, c3 = st.columns(3)
        cat = c1.selectbox("Category", ["All"] + CATEGORIES, key=f"{prefix}_cat")
        jt = c2.selectbox("Type", ["All"] + JOB_TYPES, key=f"{prefix}_jt")
        city = c3.text_input("City", key=f"{prefix}_city")
        sal = st.number_input("Min salary / month (0 = any)", 0, 10_000_000, 0, step=5000, key=f"{prefix}_sal")
    return dict(keywords=kw, category=cat, job_type=jt, city=city, min_salary=int(sal), video_only=video_only)


# ----------------------------------------------------------------------------
# Cards
# ----------------------------------------------------------------------------
def candidate_card(me, role, c, ctx, saved):
    uid = c["user_id"]
    p = get_person(uid)
    person_video_block(me, role, p, ctx)
    person_header(p, 44, extra=f"{ago(c['updated'])}")
    st.markdown(
        f'<div class="meta">📍 {esc(c["city"] or "-")} &nbsp;•&nbsp; 💼 {c["experience"] or 0} yrs '
        f'&nbsp;•&nbsp; 💰 {(c["salary"] or 0):,}/mo</div>'
        f'<div>{chips(c["skills"], 8, c["category"] or "")}</div>'
        f'<div class="meta">🎓 {esc(c["education"] or "-")}</div>'
        f'<div class="meta">{esc((c["about"] or "")[:220])}</div>',
        unsafe_allow_html=True,
    )
    if uid == me:
        st.caption("⭐ This is your profile")
        return
    c1, c2, c3 = st.columns(3)
    with c1:
        connect_btn(me, uid, f"cn_{ctx}_{uid}")
    with c2:
        cv_button(me, role, p, f"cv_{ctx}_{uid}", label="📄 CV")
    with c3:
        if role == "company":
            is_saved = uid in saved
            if st.button("★ Saved" if is_saved else "☆ Shortlist", key=f"sl_{ctx}_{uid}"):
                toggle_shortlist(me, uid)
                st.rerun()
        elif st.button("👤 Profile", key=f"pf_{ctx}_{uid}"):
            open_profile(uid)
    comments_block("video", uid, me, ctx)


def job_card(me, role, j, ctx):
    co = get_person(j["company_id"])
    has_video = exists(j.get("video_path"))
    if has_video:
        job_video_block(me, j, co, ctx)
    if co:
        person_header(co, 40, extra=ago(j["created"]))
    sal = ""
    if j["salary_min"] or j["salary_max"]:
        sal = f' &nbsp;•&nbsp; 💰 {(j["salary_min"] or 0):,} – {(j["salary_max"] or 0):,}/mo'
    st.markdown(
        f'<div class="jtitle">{esc(j["title"])}</div>'
        f'<div class="meta">📍 {esc(j["city"] or "-")} &nbsp;•&nbsp; {esc(j["job_type"] or "")}{sal}</div>'
        f'<div>{chips(j["skills"], 8, j["category"] or "")}</div>',
        unsafe_allow_html=True,
    )
    with st.expander("Job details"):
        st.markdown(f'<div class="body">{safe(j["description"])}</div>', unsafe_allow_html=True)
    job_download_button(j, f"jdl_{ctx}_{j['id']}")
    if j["company_id"] == me:
        n = q1("SELECT COUNT(*) n FROM applications WHERE job_id=?", (j["id"],))["n"]
        st.caption(f"👥 {n} applicants — manage them in Jobs → My jobs")
        return
    if not has_video:  # no video, so no action rail: show the buttons here
        c1, c2, c3 = st.columns(3)
        with c1:
            like_btn("job", j["id"], me, f"jl_{ctx}_{j['id']}")
        with c2:
            if st.button("🏢 Company", key=f"jc_{ctx}_{j['id']}"):
                open_profile(j["company_id"])
        with c3:
            if st.button("✉️ Chat", key=f"jm_{ctx}_{j['id']}"):
                goto("messages", chat_with=j["company_id"])
    if role == "seeker":
        app = q1("SELECT * FROM applications WHERE job_id=? AND seeker_id=?", (j["id"], me))
        if app:
            st.markdown(f'<span class="badge st-{app["status"]}" style="margin-left:0">✔ Applied · {app["status"]}</span>',
                        unsafe_allow_html=True)
        else:
            with st.expander("📨 Apply with my video profile"):
                with st.form(f"apply_{ctx}_{j['id']}"):
                    note = st.text_area("Message to the company (optional)", max_chars=500)
                    if st.form_submit_button("Send application"):
                        prof = get_person(me)
                        if not exists(prof.get("video_path")):
                            st.error("Please upload your video pitch in My Profile first - companies watch it with your application.")
                        else:
                            ex("INSERT OR IGNORE INTO applications(job_id,seeker_id,note) VALUES(?,?,?)",
                               (j["id"], me, note.strip()))
                            st.rerun()
    comments_block("job", j["id"], me, ctx)


# ----------------------------------------------------------------------------
# Auth
# ----------------------------------------------------------------------------
def header():
    st.markdown('<div class="logo"><span style="-webkit-text-fill-color:initial">🎬</span> JobTok</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="tagline">Watch. Connect. Get hired.</div>', unsafe_allow_html=True)


def auth_screen():
    header()
    if st.session_state.get("flash"):
        st.success(st.session_state.pop("flash"))
    if not (db_url() and storage_conf()) and os.path.isdir("/mount/src"):      # running on Streamlit Community Cloud
        st.warning("Storage is not connected: accounts and videos here are deleted whenever this app restarts. "
                   "App owner: set DATABASE_URL and SUPABASE_URL / SUPABASE_SERVICE_KEY in the app Secrets (see README).")
    tab_in, tab_up = st.tabs(["Log in", "Sign up"])
    with tab_in:
        with st.form("login"):
            email = st.text_input("Email", autocomplete="email")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Log in"):
                user = login(email, pw)
                if user:
                    st.session_state.user = user
                    remember_login(user["id"])
                    st.rerun()
                else:
                    st.error("Wrong email or password.")
        with st.expander("🔑 Forgot password?"):
            reset_flow()
    with tab_up:
        if st.session_state.get("signup_data"):
            verify_step()
        else:
            signup_step()


def reset_flow():
    rd = st.session_state.get("reset_data")
    if not rd:
        with st.form("reset_ask"):
            email = st.text_input("Your account email", key="rs_email", autocomplete="email")
            go = st.form_submit_button("Send reset code")
        if not go:
            return
        email = email.strip().lower()
        if not EMAIL_RE.match(email):
            st.error("Please enter a valid email.")
            return
        user = q1("SELECT name FROM users WHERE email=?", (email,))
        demo = None
        if user:                                   # unknown emails get the same screen, but nothing is sent
            code, err = issue_code("reset:" + email)
            if err:
                st.error(err)
                return
            if smtp_config():
                ok, err = send_code_email(email, user["name"], code, "reset")
                if not ok:
                    ex("DELETE FROM email_codes WHERE email=?", ("reset:" + email,))
                    st.error(err)
                    return
            else:
                demo = code
        st.session_state.reset_data = dict(email=email, demo_code=demo)
        st.rerun()
        return
    st.info(f"If an account exists for **{esc(rd['email'])}**, a 6-digit code was sent to it.")
    if rd.get("demo_code"):
        st.warning(f"DEMO MODE: no email account is connected, so no email was sent. Your code is: **{rd['demo_code']}**")
    with st.form("reset_do"):
        code = st.text_input("6-digit code", max_chars=6, key="rs_code")
        pw = st.text_input("New password (min 6 characters)", type="password", key="rs_pw")
        done = st.form_submit_button("Set new password")
    if done:
        if not re.fullmatch(r"\d{6}", code.strip()) or len(pw) < 6:
            st.error("Enter the 6-digit code and a new password of 6+ characters.")
        else:
            ok, err = check_code("reset:" + rd["email"], code)
            if not ok:
                st.error(err)
            else:
                salt = secrets.token_hex(8)
                ex("UPDATE users SET salt=?, pw_hash=? WHERE email=?", (salt, hash_pw(pw, salt), rd["email"]))
                ex("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE email=?)", (rd["email"],))
                st.session_state.pop("reset_data", None)
                st.success("Password changed. You can log in now.")
    if st.button("↩ Use a different email", key="rs_back"):
        st.session_state.pop("reset_data", None)
        st.rerun()


def signup_step():
    role_label = st.radio("I am a...", ["🧑‍💼 Job Seeker", "🏢 Company / Employer"], horizontal=True, key="su_role")
    with st.form("signup"):
        name = st.text_input("Full name" if "Seeker" in role_label else "Company name")
        email = st.text_input("Email ", key="su_email", autocomplete="email")
        pw = st.text_input("Password (min 6 characters)", type="password", key="su_pw")
        go = st.form_submit_button("Send verification code")
    if not go:
        return
    email = email.strip().lower()
    if not name.strip() or not EMAIL_RE.match(email) or len(pw) < 6:
        st.error("Please fill in all fields (valid email, password of 6+ characters).")
        return
    if q1("SELECT 1 x FROM users WHERE email=?", (email,)):
        st.error("This email is already registered. Please log in instead.")
        return
    code, err = issue_code(email)
    if err:
        st.error(err)
        return
    demo = None
    if smtp_config():
        ok, err = send_code_email(email, name.strip(), code)
        if not ok:
            ex("DELETE FROM email_codes WHERE email=?", (email,))      # let them retry right away
            st.error(err)
            return
    else:
        demo = code
    salt = secrets.token_hex(8)
    st.session_state.signup_data = dict(role="seeker" if "Seeker" in role_label else "company", name=name.strip(),
                                   email=email, salt=salt, pw_hash=hash_pw(pw, salt), demo_code=demo)
    st.rerun()


def verify_step():
    su = st.session_state.signup_data
    st.markdown(f"##### 📧 Check your email\nWe sent a 6-digit code to **{esc(su['email'])}**. It is valid for "
                f"{CODE_TTL // 60} minutes. Also look in your spam folder.")
    if su.get("demo_code"):
        st.warning(f"DEMO MODE: no email account is connected to this app yet, so no email was sent. "
                   f"Your code is: **{su['demo_code']}**")
        with st.expander("How do I make it send real emails?"):
            st.markdown("1. Create `.streamlit/secrets.toml` next to `app.py` (copy `secrets.toml.example`).\n"
                        "2. Fill in `SMTP_USER` and `SMTP_PASSWORD` (Gmail: use an **App Password**).\n"
                        "3. Restart the app. Run `python check_email.py you@gmail.com` to test it first.")
    with st.form("verify"):
        code = st.text_input("Verification code", max_chars=6, placeholder="123456")
        done = st.form_submit_button("✅ Verify and create account")
    if done:
        if not re.fullmatch(r"\d{6}", code.strip()):
            st.error("Enter the 6-digit code.")
        else:
            ok, err = check_code(su["email"], code)
            if not ok:
                st.error(err)
            else:
                uid, err = create_user(su["role"], su["name"], su["email"], su["salt"], su["pw_hash"])
                if err:
                    st.error(err)
                else:
                    st.session_state.user = {"id": uid, "role": su["role"], "name": su["name"], "email": su["email"]}
                    remember_login(uid)
                    st.session_state.pop("signup_data", None)
                    st.session_state.nav_to = "profile"
                    st.rerun()
    c1, c2 = st.columns(2)
    if c1.button("🔁 Resend code", key="su_resend"):
        code, err = issue_code(su["email"])
        if err:
            st.error(err)
        elif smtp_config():
            ok, err = send_code_email(su["email"], su["name"], code)
            st.success("A new code was sent.") if ok else st.error(err)
        else:
            su["demo_code"] = code
            st.rerun()
    if c2.button("✏️ Change email", key="su_back"):
        st.session_state.pop("signup_data", None)
        st.rerun()


# ----------------------------------------------------------------------------
# Page: Home (TikTok feed of people and jobs)
# ----------------------------------------------------------------------------
def home_page(me, role):
    mode = st.radio("Feed", ["👥 People", "💼 Jobs"], horizontal=True, label_visibility="collapsed", key="home_mode")
    if mode.startswith("👥"):
        people_feed(me, role)
    else:
        jobs_video_feed(me, role)


def paged(items, key, render):
    """Scroll mode with 'load more' or swipe mode with prev/next."""
    view = st.radio("View", ["⬇️ Scroll", "👆 Swipe"], horizontal=True, label_visibility="collapsed", key=f"{key}_view")
    sig = repr(len(items)) + view
    if st.session_state.get(f"{key}_sig") != sig:
        st.session_state[f"{key}_sig"] = sig
        st.session_state[f"{key}_n"] = PAGE_SIZE
        st.session_state[f"{key}_i"] = 0
    if not items:
        return
    if view.startswith("⬇️"):
        shown = st.session_state[f"{key}_n"]
        st.markdown(f'<div class="counter">{len(items)} results • scroll down ⬇️</div>', unsafe_allow_html=True)
        for it in items[:shown]:
            with st.container():
                render(it, key)
                st.divider()
        if shown < len(items):
            if st.button(f"Load more ({len(items) - shown} left)", key=f"{key}_more"):
                st.session_state[f"{key}_n"] = shown + PAGE_SIZE
                st.rerun()
        else:
            st.caption("🎉 You've seen everything.")
    else:
        i = min(st.session_state[f"{key}_i"], len(items) - 1)
        st.markdown(f'<div class="counter">{i + 1} of {len(items)}</div>', unsafe_allow_html=True)
        render(items[i], key + "sw")
        b1, b2 = st.columns(2)
        if b1.button("⬅️ Prev", disabled=i == 0, key=f"{key}_prev"):
            st.session_state[f"{key}_i"] = i - 1
            st.rerun()
        if b2.button("Next ➡️", disabled=i >= len(items) - 1, key=f"{key}_next"):
            st.session_state[f"{key}_i"] = i + 1
            st.rerun()


def people_feed(me, role):
    f = people_filters("hp")
    results = search_candidates(f)
    if not results:
        st.info("No profiles with a video match yet. Be the first to upload one!")
        return
    saved = shortlisted_ids(me) if role == "company" else set()
    paged(results, "hp", lambda c, ctx: candidate_card(me, role, c, ctx, saved))


def jobs_video_feed(me, role):
    f = job_filters("hj", video_only=False)
    results = search_jobs(f)
    if not results:
        st.info("No jobs posted yet.")
        return
    # videos first, like a TikTok feed
    results.sort(key=lambda j: not exists(j.get("video_path")))
    paged(results, "hj", lambda j, ctx: job_card(me, role, j, ctx))


# ----------------------------------------------------------------------------
# Page: Posts (LinkedIn style updates)
# ----------------------------------------------------------------------------
def posts_page(me, role):
    with st.form("new_post", clear_on_submit=True):
        body = st.text_area("Start a post", placeholder="Share an update, a tip, or that you're hiring…",
                            max_chars=1000, height=90)
        c1, c2 = st.columns(2)
        img = c1.file_uploader("Photo (optional)", type=["jpg", "jpeg", "png"])
        vid = c2.file_uploader(f"Video (max {MAX_SECONDS}s)", type=["mp4", "mov", "webm", "m4v"])
        if st.form_submit_button("📣 Post"):
            if not body.strip():
                st.error("Write something first.")
            else:
                path = vpath = None
                if img is not None:
                    path, err = save_image(img)
                    if err:
                        st.error(err)
                        return
                if vid is not None:
                    vpath, err = save_video(vid)
                    if err:
                        drop_file(path)
                        st.error(err)
                        return
                ex("INSERT INTO posts(user_id,body,image_path,video_path) VALUES(?,?,?,?)",
                   (me, body.strip(), path, vpath))
                st.rerun()

    scope = st.radio("Show", ["🌍 Everyone", "🤝 My network"], horizontal=True, label_visibility="collapsed")
    if scope.startswith("🤝"):
        ids = my_connection_ids(me) + [me]
        marks = ",".join("?" * len(ids))
        posts = q(f"SELECT * FROM posts WHERE user_id IN ({marks}) ORDER BY id DESC LIMIT 50", ids)
    else:
        posts = q("SELECT * FROM posts ORDER BY id DESC LIMIT 50")
    if not posts:
        st.info("No posts yet. Share the first one!")
    for po in posts:
        with st.container(border=True):
            author = get_person(po["user_id"])
            if not author:
                continue
            person_header(author, 44, extra=ago(po["created"]))
            st.markdown(f'<div class="body">{safe(po["body"])}</div>', unsafe_allow_html=True)
            if exists(po.get("video_path")):
                with st.container(key=f"vc_post_{po['id']}"):
                    video_player(po["video_path"], title=author["name"], subtitle=headline_of(author))
            if exists(po["image_path"]):
                st.image(po["image_path"])
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                like_btn("post", po["id"], me, f"pl_{po['id']}")
            with c2:
                if po["user_id"] != me and st.button("👤 Profile", key=f"pp_{po['id']}"):
                    open_profile(po["user_id"])
            with c3:
                if po["user_id"] != me:
                    cv_button(me, role, author, f"pcv_{po['id']}", label="📄 CV")
            with c4:
                if po["user_id"] == me and st.button("🗑 Delete", key=f"pd_{po['id']}"):
                    drop_file(po["image_path"])
                    drop_file(po.get("video_path"))
                    ex("DELETE FROM posts WHERE id=?", (po["id"],))
                    st.rerun()
            comments_block("post", po["id"], me, "ps")


# ----------------------------------------------------------------------------
# Page: Jobs
# ----------------------------------------------------------------------------
def jobs_page(me, role):
    if role == "seeker":
        tab_browse, tab_apps = st.tabs(["🔍 Browse jobs", "📨 My applications"])
        with tab_browse:
            browse_jobs(me, role)
        with tab_apps:
            my_applications(me)
    else:
        tab_browse, tab_post, tab_mine = st.tabs(["🔍 Browse jobs", "➕ Post a job", "📋 My jobs & applicants"])
        with tab_browse:
            browse_jobs(me, role)
        with tab_post:
            post_job_form(me)
        with tab_mine:
            my_jobs(me)


def browse_jobs(me, role):
    f = job_filters("bj")
    results = search_jobs(f)
    if not results:
        st.info("No jobs match. Try different filters.")
    for j in results[:30]:
        with st.container(border=True):
            job_card(me, role, j, "bj")


def my_applications(me):
    apps = q("""SELECT a.*, j.title, j.city, j.company_id, u.name AS company_name
                FROM applications a JOIN jobs j ON j.id=a.job_id JOIN users u ON u.id=j.company_id
                WHERE a.seeker_id=? ORDER BY a.id DESC""", (me,))
    if not apps:
        st.info("You haven't applied to any job yet. Browse jobs and tap Apply.")
    for a in apps:
        with st.container(border=True):
            st.markdown(f'<div class="jtitle">{esc(a["title"])}</div>'
                        f'<div class="meta">{esc(a["company_name"])} • 📍 {esc(a["city"] or "-")} • applied {ago(a["created"])}</div>'
                        f'<span class="badge st-{a["status"]}" style="margin-left:0">{a["status"]}</span>',
                        unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            if b1.button("🏢 Company", key=f"ac_{a['id']}"):
                open_profile(a["company_id"])
            if b2.button("✉️ Message", key=f"am_{a['id']}"):
                goto("messages", chat_with=a["company_id"])
    ex("UPDATE applications SET seen=1 WHERE seeker_id=?", (me,))


def post_job_form(me):
    with st.form("post_job", clear_on_submit=True):
        title = st.text_input("Job title *")
        c1, c2 = st.columns(2)
        cat = c1.selectbox("Category", CATEGORIES)
        jt = c2.selectbox("Type", JOB_TYPES)
        c3, c4, c5 = st.columns(3)
        city = c3.text_input("City *")
        smin = c4.number_input("Salary from / month", 0, 10_000_000, 0, step=5000)
        smax = c5.number_input("Salary to / month", 0, 10_000_000, 0, step=5000)
        skills = st.text_input("Required skills (comma separated)")
        desc = st.text_area("Description *", height=140, max_chars=3000)
        video = st.file_uploader(f"Job video (optional, max {MAX_SECONDS}s) - show your team and office!",
                                 type=["mp4", "mov", "webm", "m4v"])
        if st.form_submit_button("🚀 Publish job"):
            if not (title.strip() and city.strip() and desc.strip()):
                st.error("Title, city and description are required.")
                return
            vpath = None
            if video is not None:
                vpath, err = save_video(video)
                if err:
                    st.error(err)
                    return
            ex("""INSERT INTO jobs(company_id,title,category,city,job_type,salary_min,salary_max,skills,description,video_path)
                  VALUES(?,?,?,?,?,?,?,?,?,?)""",
               (me, title.strip(), cat, city.strip(), jt, int(smin), int(smax), skills.strip(), desc.strip(), vpath))
            st.success("Job published! Job seekers can now see and apply.")


def my_jobs(me):
    jobs = q("SELECT * FROM jobs WHERE company_id=? ORDER BY id DESC", (me,))
    if not jobs:
        st.info("You haven't posted a job yet.")
    for j in jobs:
        apps = q("SELECT * FROM applications WHERE job_id=? ORDER BY id DESC", (j["id"],))
        new = sum(1 for a in apps if a["status"] == "Applied")
        label = f"{'🟢' if j['active'] else '⚪'} {j['title']} — {len(apps)} applicants" + (f" ({new} new)" if new else "")
        with st.expander(label):
            if st.button("Close job" if j["active"] else "Reopen job", key=f"cl_{j['id']}"):
                ex("UPDATE jobs SET active=? WHERE id=?", (0 if j["active"] else 1, j["id"]))
                st.rerun()
            if not apps:
                st.caption("No applications yet.")
            for a in apps:
                with st.container(border=True):
                    sp = get_person(a["seeker_id"])
                    if not sp:
                        continue
                    person_header(sp, 44, extra=f"applied {ago(a['created'])}")
                    if a["note"]:
                        st.markdown(f'<div class="body">{safe(a["note"])}</div>', unsafe_allow_html=True)
                    show_person_video(sp)
                    cv_button(me, "company", sp, f"acv_{a['id']}")
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    new_status = c1.selectbox("Status", STATUSES, index=STATUSES.index(a["status"]),
                                              key=f"stt_{a['id']}", label_visibility="collapsed")
                    if c2.button("Save", key=f"sv_{a['id']}"):
                        ex("UPDATE applications SET status=?, seen=0 WHERE id=?", (new_status, a["id"]))
                        st.rerun()
                    if c3.button("👤", key=f"vp_{a['id']}"):
                        open_profile(a["seeker_id"])
                    if c4.button("✉️", key=f"vm_{a['id']}"):
                        goto("messages", chat_with=a["seeker_id"])


# ----------------------------------------------------------------------------
# Page: Network
# ----------------------------------------------------------------------------
def network_page(me, role):
    inv = q("SELECT * FROM connections WHERE to_id=? AND status='pending' ORDER BY id DESC", (me,))
    ids = my_connection_ids(me)
    tab_inv, tab_con, tab_disc = st.tabs([f"📩 Invitations ({len(inv)})", f"🤝 Connections ({len(ids)})", "🔍 Discover"])
    with tab_inv:
        if not inv:
            st.info("No pending invitations.")
        for r in inv:
            with st.container(border=True):
                p = get_person(r["from_id"])
                if not p:
                    continue
                person_header(p, 44, extra=f"wants to connect • {ago(r['created'])}")
                c1, c2, c3 = st.columns(3)
                if c1.button("✅ Accept", key=f"ia_{r['id']}"):
                    ex("UPDATE connections SET status='accepted' WHERE id=?", (r["id"],))
                    st.rerun()
                if c2.button("✖ Ignore", key=f"ii_{r['id']}"):
                    ex("DELETE FROM connections WHERE id=?", (r["id"],))
                    st.rerun()
                if c3.button("👤 Profile", key=f"ip_{r['id']}"):
                    open_profile(r["from_id"])
    with tab_con:
        if not ids:
            st.info("No connections yet. Use Discover to find people.")
        for uid in ids:
            p = get_person(uid)
            if not p:
                continue
            with st.container(border=True):
                person_header(p, 44)
                c1, c2 = st.columns(2)
                if c1.button("👤 Profile", key=f"cp_{uid}"):
                    open_profile(uid)
                if c2.button("✉️ Message", key=f"cm_{uid}"):
                    goto("messages", chat_with=uid)
    with tab_disc:
        text = st.text_input("Search people and companies", placeholder="name, skill, title, industry…", key="disc_q")
        kind = st.radio("Show", ["All", "Job seekers", "Companies"], horizontal=True, key="disc_kind")
        rows = q("""SELECT u.id, u.role FROM users u
                    LEFT JOIN seekers s ON s.user_id=u.id LEFT JOIN companies c ON c.user_id=u.id
                    WHERE u.id != ? AND (? = 'All' OR (? = 'Job seekers' AND u.role='seeker')
                          OR (? = 'Companies' AND u.role='company'))
                      AND LOWER(COALESCE(u.name,'')||' '||COALESCE(s.headline,'')||' '||COALESCE(s.title,'')||' '||
                          COALESCE(s.skills,'')||' '||COALESCE(s.city,'')||' '||COALESCE(c.industry,'')||' '||
                          COALESCE(c.city,'')) LIKE ?
                    ORDER BY u.id DESC LIMIT 20""",
                 (me, kind, kind, kind, f"%{text.strip().lower()}%"))
        if not rows:
            st.info("Nobody found.")
        for r in rows:
            p = get_person(r["id"])
            with st.container(border=True):
                person_header(p, 44)
                c1, c2, c3 = st.columns(3)
                with c1:
                    connect_btn(me, r["id"], f"dc_{r['id']}")
                if c2.button("👤 Profile", key=f"dp_{r['id']}"):
                    open_profile(r["id"])
                if c3.button("✉️ Chat", key=f"dm_{r['id']}"):
                    goto("messages", chat_with=r["id"])


# ----------------------------------------------------------------------------
# Page: Messages
# ----------------------------------------------------------------------------
def messages_page(me, role):
    rows = q("""SELECT pid FROM (
                   SELECT CASE WHEN from_id=? THEN to_id ELSE from_id END AS pid, MAX(id) AS last_id
                   FROM messages WHERE from_id=? OR to_id=? GROUP BY CASE WHEN from_id=? THEN to_id ELSE from_id END
                ) t ORDER BY last_id DESC""", (me, me, me, me))
    options = [r["pid"] for r in rows]
    for cid in my_connection_ids(me):
        if cid not in options:
            options.append(cid)
    want = st.session_state.get("chat_with")
    if want and want not in options:
        options.insert(0, want)
    if not options:
        st.info("No conversations yet. Connect with people, then say hello! 👋")
        return
    names = {u["id"]: u["name"] for u in q("SELECT id, name FROM users")}
    if st.session_state.get("chat_with") not in options:
        st.session_state.chat_with = options[0]
    other = st.selectbox("Conversation", options, format_func=lambda i: names.get(i, "?"), key="chat_with")
    p = get_person(other)
    person_header(p, 40)
    ex("UPDATE messages SET is_read=1 WHERE to_id=? AND from_id=?", (me, other))
    msgs = q("""SELECT * FROM messages WHERE (from_id=? AND to_id=?) OR (from_id=? AND to_id=?)
                ORDER BY id DESC LIMIT 60""", (me, other, other, me))[::-1]
    if not msgs:
        st.caption("Say hello 👋")
    for m in msgs:
        side = "me" if m["from_id"] == me else "them"
        st.markdown(f'<div class="bubble {side}">{safe(m["body"])}<div class="time">{ago(m["created"])}</div></div>',
                    unsafe_allow_html=True)
    with st.form("send_msg", clear_on_submit=True):
        body = st.text_input("Message", placeholder="Type a message…", label_visibility="collapsed", max_chars=1000)
        c1, c2 = st.columns([3, 1])
        if c1.form_submit_button("Send"):
            if body.strip():
                ex("INSERT INTO messages(from_id,to_id,body) VALUES(?,?,?)", (me, other, body.strip()))
                st.rerun()
        if c2.form_submit_button("🔄"):
            st.rerun()


# ----------------------------------------------------------------------------
# Profile view (anyone's profile)
# ----------------------------------------------------------------------------
def profile_view(uid, me, role):
    p = get_person(uid)
    if not p:
        st.error("Profile not found.")
        return
    own = uid == me
    person_header(p, 76)
    if p["role"] == "seeker":
        st.markdown(
            f'<div class="meta">📍 {esc(p.get("city") or "-")} &nbsp;•&nbsp; 💼 {p.get("experience") or 0} yrs '
            f'&nbsp;•&nbsp; 💰 {(p.get("salary") or 0):,}/mo expected</div>', unsafe_allow_html=True)
    else:
        site = f' &nbsp;•&nbsp; 🌐 {esc(p["website"])}' if p.get("website") else ""
        st.markdown(f'<div class="meta">📍 {esc(p.get("city") or "-")}{site}</div>', unsafe_allow_html=True)

    if not own:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            connect_btn(me, uid, f"pv_cn_{uid}")
        with c2:
            if st.button("✉️ Message", key=f"pv_ms_{uid}"):
                goto("messages", chat_with=uid)
        with c3:
            if p["role"] == "seeker":
                like_btn("video", uid, me, f"pv_lk_{uid}")
        with c4:
            if role == "company" and p["role"] == "seeker":
                saved = uid in shortlisted_ids(me)
                if st.button("★ Saved" if saved else "☆ Shortlist", key=f"pv_sl_{uid}"):
                    toggle_shortlist(me, uid)
                    st.rerun()

    if p["role"] == "seeker":
        show_person_video(p)
        cv_button(me, role, p, f"pvcv_{uid}", label="📄 Download CV (PDF)")
        if p.get("about"):
            st.markdown("##### About")
            st.markdown(f'<div class="body">{safe(p["about"])}</div>', unsafe_allow_html=True)
        if p.get("skills"):
            st.markdown("##### Skills")
            st.markdown(chips(p["skills"], 20), unsafe_allow_html=True)
        exps = q("SELECT * FROM experiences WHERE user_id=? ORDER BY id DESC", (uid,))
        if exps:
            st.markdown("##### Experience")
            for e in exps:
                st.markdown(f'<div class="body"><b>{esc(e["role"])}</b> · {esc(e["company"] or "")}'
                            f'<div class="meta">{esc(e["start"] or "")} – {esc(e["end"] or "Present")}</div>'
                            f'{safe(e["description"])}</div>', unsafe_allow_html=True)
        if p.get("education"):
            st.markdown("##### Education")
            st.markdown(f'<div class="body">🎓 {esc(p["education"])}</div>', unsafe_allow_html=True)
        can_see = contact_visible(me, role, uid)
        st.markdown("##### Contact")
        if can_see:
            st.markdown(f'<div class="body">📧 {esc(p["email"])}<br>📱 {esc(p.get("phone") or "not provided")}</div>',
                        unsafe_allow_html=True)
        else:
            st.caption("🔒 Connect with this person (or shortlist them as a company) to see contact details.")
        comments_block("video", uid, me, "pv")
    else:
        if p.get("about"):
            st.markdown("##### About us")
            st.markdown(f'<div class="body">{safe(p["about"])}</div>', unsafe_allow_html=True)
        jobs = search_jobs({}, company_id=uid)
        st.markdown(f"##### Open positions ({len(jobs)})")
        for j in jobs:
            with st.container(border=True):
                job_card(me, role, j, "pv")


# ----------------------------------------------------------------------------
# Page: My profile (edit)
# ----------------------------------------------------------------------------
def completeness(p, n_exp):
    checks = [
        ("Profile photo", bool(p.get("photo_path"))), ("Headline", bool(p.get("headline"))),
        ("Job title", bool(p.get("title"))), ("Skills", bool(p.get("skills"))),
        ("About", bool(p.get("about"))), ("City", bool(p.get("city"))),
        ("Education", bool(p.get("education"))), ("Video pitch", exists(p.get("video_path"))),
        ("Work experience", n_exp > 0), ("Phone", bool(p.get("phone"))),
    ]
    done = sum(1 for _, ok in checks if ok)
    return done / len(checks), [n for n, ok in checks if not ok]


def delete_account(uid):
    """Permanently remove a user and everything that belongs to them (rows AND files)."""
    u = q1("SELECT email FROM users WHERE id=?", (uid,))
    if not u:
        return
    files = []
    for r in q("SELECT video_path, photo_path FROM seekers WHERE user_id=?", (uid,)):
        files += [r["video_path"], r["photo_path"]]
    files += [r["photo_path"] for r in q("SELECT photo_path FROM companies WHERE user_id=?", (uid,))]
    posts = q("SELECT id, image_path, video_path FROM posts WHERE user_id=?", (uid,))
    jobs = q("SELECT id, video_path FROM jobs WHERE company_id=?", (uid,))
    for po in posts:
        files += [po["image_path"], po["video_path"]]
        ex("DELETE FROM likes WHERE kind='post' AND target_id=?", (po["id"],))
        ex("DELETE FROM comments WHERE kind='post' AND target_id=?", (po["id"],))
    for j in jobs:
        files.append(j["video_path"])
        ex("DELETE FROM applications WHERE job_id=?", (j["id"],))
        ex("DELETE FROM likes WHERE kind='job' AND target_id=?", (j["id"],))
        ex("DELETE FROM comments WHERE kind='job' AND target_id=?", (j["id"],))
    ex("DELETE FROM likes WHERE kind='video' AND target_id=?", (uid,))       # likes/comments on their video profile
    ex("DELETE FROM comments WHERE kind='video' AND target_id=?", (uid,))
    for sql in ("DELETE FROM likes WHERE user_id=?", "DELETE FROM comments WHERE user_id=?",
                "DELETE FROM posts WHERE user_id=?", "DELETE FROM jobs WHERE company_id=?",
                "DELETE FROM experiences WHERE user_id=?", "DELETE FROM seekers WHERE user_id=?",
                "DELETE FROM companies WHERE user_id=?", "DELETE FROM applications WHERE seeker_id=?",
                "DELETE FROM shortlist WHERE company_id=?", "DELETE FROM shortlist WHERE seeker_id=?"):
        ex(sql, (uid,))
    ex("DELETE FROM connections WHERE from_id=? OR to_id=?", (uid, uid))
    ex("DELETE FROM messages WHERE from_id=? OR to_id=?", (uid, uid))
    ex("DELETE FROM email_codes WHERE email=? OR email=?", (u["email"], "reset:" + u["email"]))
    ex("DELETE FROM sessions WHERE user_id=?", (uid,))
    ex("DELETE FROM users WHERE id=?", (uid,))
    for f in files:
        drop_file(f)


def delete_account_ui(me):
    with st.expander("⚠️ Delete my account"):
        st.markdown("Your account stays on JobTok until **you** delete it. Deleting removes your profile, videos, "
                    "photos, posts, jobs, messages and connections **forever**. This cannot be undone.")
        with st.form("delete_account"):
            pw = st.text_input("Type your password to confirm", type="password")
            sure = st.checkbox("I understand this is permanent")
            go = st.form_submit_button("🗑 Delete my account forever")
        if go:
            user = st.session_state.get("user") or {}
            if not sure:
                st.error("Please tick the box to confirm.")
            elif not login(user.get("email", ""), pw):
                st.error("Wrong password.")
            else:
                delete_account(me)
                st.session_state.clear()
                st.session_state["_cookie_clear"] = True
                st.session_state["flash"] = "Your account and all its data were deleted."
                st.rerun()


def logout_button(key):
    if st.button("🚪 Log out", key=key):
        do_logout()


def profile_page(me, role):
    p = get_person(me)
    if role == "seeker":
        n_exp = q1("SELECT COUNT(*) n FROM experiences WHERE user_id=?", (me,))["n"]
        pct, missing = completeness(p, n_exp)
        st.markdown(f"##### 💪 Profile strength: {int(pct * 100)}%")
        st.progress(pct)
        if missing:
            st.caption("Add: " + ", ".join(missing))
        tab_edit, tab_exp, tab_prev = st.tabs(["✏️ Edit", "💼 Experience", "👁 Preview"])
        with tab_edit:
            seeker_edit(me, p)
        with tab_exp:
            experience_tab(me)
        with tab_prev:
            profile_view(me, me, role)
    else:
        tab_edit, tab_prev = st.tabs(["✏️ Edit", "👁 Preview"])
        with tab_edit:
            company_edit(me, p)
        with tab_prev:
            profile_view(me, me, role)
    st.divider()
    logout_button("logout_profile")
    delete_account_ui(me)


def seeker_edit(me, p):
    if exists(p.get("video_path")):
        show_person_video(p)
    else:
        st.info(f"Add your {MAX_SECONDS}-second video pitch - profiles with a video appear on the Home feed.")
    with st.expander("💡 Tips for a great 30-second video"):
        st.markdown("- Record vertically with your phone (selfie mode, good light)\n"
                    "- Say who you are, what you do, your top skills and the job you want\n"
                    "- Smile, speak clearly, finish before 30 seconds\n- Formats: MP4, MOV, WEBM")
    with st.form("profile"):
        c1, c2 = st.columns(2)
        photo = c1.file_uploader("Profile photo", type=["jpg", "jpeg", "png"])
        video = c2.file_uploader(f"Video pitch (max {MAX_SECONDS}s)", type=["mp4", "mov", "webm", "m4v"])
        name = st.text_input("Full name *", p["name"])
        headline = st.text_input("Headline", p.get("headline") or "", placeholder="Python developer | Open to remote roles", max_chars=120)
        title = st.text_input("Job title you want *", p.get("title") or "", placeholder="e.g. Python Developer")
        category = st.selectbox("Category *", CATEGORIES,
                                index=CATEGORIES.index(p["category"]) if p.get("category") in CATEGORIES else 0)
        skills = st.text_input("Skills (comma separated) *", p.get("skills") or "", placeholder="python, sql, communication")
        c3, c4 = st.columns(2)
        experience = c3.number_input("Experience (years)", 0, 50, int(p.get("experience") or 0))
        salary = c4.number_input("Expected salary / month", 0, 10_000_000, int(p.get("salary") or 0), step=5000)
        city = st.text_input("City *", p.get("city") or "", placeholder="Lahore")
        education = st.text_input("Education", p.get("education") or "", placeholder="BS Computer Science")
        phone = st.text_input("Phone / WhatsApp", p.get("phone") or "")
        about = st.text_area("About you", p.get("about") or "", height=100, max_chars=500)
        open_to_work = st.checkbox("🟢 Open to work", value=bool(p.get("open_to_work", 1)))
        submitted = st.form_submit_button("💾 Save profile")
    if not submitted:
        return
    if not (name.strip() and title.strip() and skills.strip() and city.strip()):
        st.error("Name, job title, skills and city are required.")
        return
    video_path, photo_path = p.get("video_path"), p.get("photo_path")
    if video is not None:
        new, err = save_video(video)
        if err:
            st.error(err)
            return
        drop_file(video_path)
        video_path = new
    if photo is not None:
        new, err = save_image(photo, size=(256, 256))
        if err:
            st.error(err)
            return
        drop_file(photo_path)
        photo_path = new
    ex("UPDATE users SET name=? WHERE id=?", (name.strip(), me))
    st.session_state.user["name"] = name.strip()
    ex("""INSERT INTO seekers(user_id,headline,title,category,skills,experience,city,salary,education,about,
                             phone,video_path,photo_path,open_to_work,updated)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
          ON CONFLICT(user_id) DO UPDATE SET headline=excluded.headline, title=excluded.title,
            category=excluded.category, skills=excluded.skills, experience=excluded.experience,
            city=excluded.city, salary=excluded.salary, education=excluded.education, about=excluded.about,
            phone=excluded.phone, video_path=excluded.video_path, photo_path=excluded.photo_path,
            open_to_work=excluded.open_to_work, updated=CURRENT_TIMESTAMP""",
       (me, headline.strip(), title.strip(), category, skills.strip(), int(experience), city.strip(), int(salary),
        education.strip(), about.strip(), phone.strip(), video_path, photo_path, 1 if open_to_work else 0))
    st.success("Profile saved! 🎉")
    st.rerun()


def experience_tab(me):
    exps = q("SELECT * FROM experiences WHERE user_id=? ORDER BY id DESC", (me,))
    for e in exps:
        with st.container(border=True):
            st.markdown(f'<b>{esc(e["role"])}</b> · {esc(e["company"] or "")}'
                        f'<div class="meta">{esc(e["start"] or "")} – {esc(e["end"] or "Present")}</div>'
                        f'<div>{safe(e["description"])}</div>', unsafe_allow_html=True)
            if st.button("🗑 Remove", key=f"xd_{e['id']}"):
                ex("DELETE FROM experiences WHERE id=?", (e["id"],))
                st.rerun()
    with st.form("add_exp", clear_on_submit=True):
        st.markdown("**Add experience**")
        role_ = st.text_input("Role *", placeholder="Frontend Developer")
        company = st.text_input("Company", placeholder="Acme Pvt Ltd")
        c1, c2 = st.columns(2)
        start = c1.text_input("From", placeholder="2021")
        end = c2.text_input("To", placeholder="2024 or leave empty for Present")
        desc = st.text_area("What did you do?", max_chars=500, height=80)
        if st.form_submit_button("➕ Add"):
            if role_.strip():
                ex('INSERT INTO experiences(user_id,role,company,start,"end",description) VALUES(?,?,?,?,?,?)',
                   (me, role_.strip(), company.strip(), start.strip(), end.strip(), desc.strip()))
                st.rerun()
            else:
                st.error("Role is required.")


def company_edit(me, p):
    with st.form("company_profile"):
        logo = st.file_uploader("Company logo", type=["jpg", "jpeg", "png"])
        name = st.text_input("Company name *", p["name"])
        c1, c2 = st.columns(2)
        industry = c1.text_input("Industry", p.get("industry") or "", placeholder="Software, Retail, Healthcare…")
        size = c2.selectbox("Company size", COMPANY_SIZES,
                            index=COMPANY_SIZES.index(p["size"]) if p.get("size") in COMPANY_SIZES else 0)
        c3, c4 = st.columns(2)
        city = c3.text_input("City", p.get("city") or "")
        website = c4.text_input("Website", p.get("website") or "")
        about = st.text_area("About the company", p.get("about") or "", height=120, max_chars=1000)
        if st.form_submit_button("💾 Save company page"):
            if not name.strip():
                st.error("Company name is required.")
                return
            photo = p.get("photo_path")
            if logo is not None:
                new, err = save_image(logo, size=(256, 256))
                if err:
                    st.error(err)
                    return
                drop_file(photo)
                photo = new
            ex("UPDATE users SET name=? WHERE id=?", (name.strip(), me))
            st.session_state.user["name"] = name.strip()
            ex("""INSERT INTO companies(user_id,industry,size,website,city,about,photo_path) VALUES(?,?,?,?,?,?,?)
                  ON CONFLICT(user_id) DO UPDATE SET industry=excluded.industry, size=excluded.size,
                    website=excluded.website, city=excluded.city, about=excluded.about, photo_path=excluded.photo_path""",
               (me, industry.strip(), size, website.strip(), city.strip(), about.strip(), photo))
            st.success("Company page saved! 🎉")
            st.rerun()


# ----------------------------------------------------------------------------
# Page: Shortlist (companies)
# ----------------------------------------------------------------------------
def shortlist_page(me, role):
    ids = list(shortlisted_ids(me))
    if not ids:
        st.info("Tap ☆ Shortlist on a candidate to save them here.")
    for uid in ids:
        p = get_person(uid)
        if not p:
            continue
        with st.container(border=True):
            person_header(p, 44)
            show_person_video(p)
            st.markdown(f'<div class="body">📧 {esc(p["email"])}<br>📱 {esc(p.get("phone") or "not provided")}</div>',
                        unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            if c1.button("👤 Profile", key=f"slp_{uid}"):
                open_profile(uid)
            if c2.button("✉️ Message", key=f"slm_{uid}"):
                goto("messages", chat_with=uid)
            with c3:
                cv_button(me, role, p, f"slcv_{uid}", label="📄 CV")
            if c4.button("Remove", key=f"slr_{uid}"):
                toggle_shortlist(me, uid)
                st.rerun()


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def counts(me, role):
    n = {}
    n["network"] = q1("SELECT COUNT(*) n FROM connections WHERE to_id=? AND status='pending'", (me,))["n"]
    n["messages"] = q1("SELECT COUNT(*) n FROM messages WHERE to_id=? AND is_read=0", (me,))["n"]
    if role == "company":
        n["jobs"] = q1("""SELECT COUNT(*) n FROM applications a JOIN jobs j ON j.id=a.job_id
                          WHERE j.company_id=? AND a.status='Applied'""", (me,))["n"]
    else:
        n["jobs"] = q1("SELECT COUNT(*) n FROM applications WHERE seeker_id=? AND seen=0", (me,))["n"]
    return n


def main():
    init_db()
    user = st.session_state.get("user")
    if not user and not st.session_state.get("_cookie_clear"):
        user = restore_login()
        if user:
            st.session_state.user = user
    if not user:
        auth_screen()
        sync_cookie()
        return
    me, role = user["id"], user["role"]
    if not q1("SELECT 1 x FROM users WHERE id=?", (me,)):
        st.session_state.clear()
        st.rerun()

    pages = {
        "home": ("🏠 Home", home_page),
        "posts": ("📰 Posts", posts_page),
        "jobs": ("💼 Jobs", jobs_page),
        "network": ("🤝 Network", network_page),
        "messages": ("✉️ Chat", messages_page),
    }
    if role == "company":
        pages["shortlist"] = ("⭐ Saved", shortlist_page)
        pages["profile"] = ("🏢 Company", profile_page)
    else:
        pages["profile"] = ("👤 Profile", profile_page)

    if "nav_to" in st.session_state:
        st.session_state.page = st.session_state.pop("nav_to")
    if st.session_state.get("page") not in pages:
        st.session_state.page = "home"

    n = counts(me, role)

    def label(k):
        icon, text = pages[k][0].split(" ", 1)
        return f"{icon} {text}{'🔴' if n.get(k) else ''}"

    def nav_changed():
        st.session_state.view_uid = None

    with st.sidebar:
        me_p = get_person(me)
        st.markdown(f'<div class="phead">{avatar_html(me_p, 44)}<div><div class="name">{esc(user["name"])}</div>'
                    f'<div class="meta">{"Company" if role == "company" else "Job seeker"}</div></div></div>',
                    unsafe_allow_html=True)
        st.caption("Use the menu bar at the top to move around.")
        if st.button("Log out"):
            do_logout()

    nav_style()
    sync_cookie()
    header()
    st.radio("Menu", list(pages), format_func=label, key="page", horizontal=True, on_change=nav_changed,
             label_visibility="collapsed")
    view_uid = st.session_state.get("view_uid")
    if view_uid:
        if st.button("← Back"):
            st.session_state.view_uid = None
            st.rerun()
        profile_view(view_uid, me, role)
    else:
        pages[st.session_state.page][1](me, role)


main()
