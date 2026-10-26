# JobTok update - ONLY the code that changed

Open `app.py` in GitHub (pencil icon) and apply the changes below **from top to bottom**, then press *Commit changes*. Each change says exactly where it goes - use Ctrl+F in the editor to find the function name.

> If a **Find** text is not found, your file differs from mine. In that case simply replace the whole `app.py` with the full file I sent.

**26 changes in app.py.** (The other small files are listed in my message.)


---
## Change 1 (REPLACE) - imports
REPLACE the import lines at the very top of the file (everything from the first `import` down to the last import / `psycopg2 = None` line) with:

```python
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
```

---
## Change 2 (EDIT) - nav_style
Inside function `nav_style` make this change:

**Find:**
```python
    [class*="st-key-vc_"] {{ position: relative; }}
```
**Replace with:**
```python
    [class*="st-key-vc_"] {{ position: relative; width: 100% !important; max-width: 420px; margin: 0 auto; }}
```

---
## Change 3 (EDIT) - SCHEMA
Inside the block `SCHEMA = ...` make these 3 changes:

**Find:**
```python
    user_id INTEGER, role TEXT, company TEXT, start TEXT, end TEXT, description TEXT
```
**Replace with:**
```python
    user_id INTEGER, role TEXT, company TEXT, start TEXT, "end" TEXT, description TEXT
```

**Find:**
```python
    user_id INTEGER, body TEXT, image_path TEXT,
```
**Replace with:**
```python
    user_id INTEGER, body TEXT, image_path TEXT, video_path TEXT,
```

**Find:**
```python
    email TEXT PRIMARY KEY, salt TEXT, code_hash TEXT, expires REAL, attempts INTEGER DEFAULT 0,
    last_sent REAL, window_start REAL, sends INTEGER DEFAULT 0
```
**Replace with:**
```python
    email TEXT PRIMARY KEY, salt TEXT, code_hash TEXT, expires DOUBLE PRECISION, attempts INTEGER DEFAULT 0,
    last_sent DOUBLE PRECISION, window_start DOUBLE PRECISION, sends INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions(
    token_hash TEXT PRIMARY KEY, user_id INTEGER, created DOUBLE PRECISION, expires DOUBLE PRECISION
```

---
## Change 4 (ADD) - ID_TABLES, INTEGRITY_ERRORS, _pg_pool, _pg_sql, _run_pg, db_url
ADD this NEW code right AFTER the end of the block `SCHEMA = ...` (leave a blank line between):

```python
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
```

---
## Change 5 (EDIT) - _run
Inside function `_run` make this change:

**Find this line (keep it) and paste the new lines right AFTER it:**
```python
def _run(sql, params=(), fetch=True):
```
**New lines to add:**
```python
    if db_url():
        return _run_pg(sql, params, fetch)
```

---
## Change 6 (EDIT) - init_db
Inside function `init_db` make these 2 changes:

**Find this line (keep it) and paste the new lines right AFTER it:**
```python
def init_db():
```
**New lines to add:**
```python
    if db_url():
        for stmt in SCHEMA.split(";"):
            if stmt.strip():
                ex(stmt)
        ex("ALTER TABLE posts ADD COLUMN IF NOT EXISTS video_path TEXT")
        return True
```

**Find:**
```python
    cols = {r["name"] for r in q("PRAGMA table_info(seekers)")}
    for col, typ in [("headline", "TEXT"), ("photo_path", "TEXT"), ("open_to_work", "INTEGER DEFAULT 1")]:
        if col not in cols:
            ex(f"ALTER TABLE seekers ADD COLUMN {col} {typ}")
```
**Replace with:**
```python
    for table, wanted in [("seekers", [("headline", "TEXT"), ("photo_path", "TEXT"), ("open_to_work", "INTEGER DEFAULT 1")]),
                          ("posts", [("video_path", "TEXT")])]:
        cols = {r["name"] for r in q(f"PRAGMA table_info({table})")}
        for col, typ in wanted:
            if col not in cols:
                ex(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
```

---
## Change 7 (EDIT) - create_user
Inside function `create_user` make this change:

**Find:**
```python
    except sqlite3.IntegrityError:
```
**Replace with:**
```python
    except INTEGRITY_ERRORS:
```

---
## Change 8 (EDIT) - issue_code
Inside function `issue_code` make this change:

**Find:**
```python
    ex("""INSERT OR REPLACE INTO email_codes(email,salt,code_hash,expires,attempts,last_sent,window_start,sends)
          VALUES(?,?,?,?,0,?,?,?)""", (email, salt, _code_hash(salt, code), now + CODE_TTL, now, window, sends))
```
**Replace with:**
```python
    ex("""INSERT INTO email_codes(email,salt,code_hash,expires,attempts,last_sent,window_start,sends)
          VALUES(?,?,?,?,0,?,?,?)
          ON CONFLICT(email) DO UPDATE SET salt=excluded.salt, code_hash=excluded.code_hash,
            expires=excluded.expires, attempts=0, last_sent=excluded.last_sent,
            window_start=excluded.window_start, sends=excluded.sends""",
       (email, salt, _code_hash(salt, code), now + CODE_TTL, now, window, sends))
```

---
## Change 9 (ADD) - COOKIE, LOGIN_DAYS, _tok_hash, do_logout, forget_login, remember_login, restore_login, sync_cookie
ADD this NEW code right AFTER the end of function `login` (leave a blank line between):

```python
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
```

---
## Change 10 (ADD) - MAX_UPLOAD_MB, MIME, _ensure_bucket, is_url, storage_conf, store_file
ADD this NEW code right AFTER the end of function `video_duration` (leave a blank line between):

```python
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
```

---
## Change 11 (EDIT) - save_video
Inside function `save_video` make these 2 changes:

**Find:**
```python
    """Validate (<= 30 s) and store the video. Returns (path, error)."""
```
**Replace with:**
```python
    """Validate (size, <= 30 s) and store the video. Returns (path_or_url, error)."""
    if uploaded.size > MAX_UPLOAD_MB * 1024 * 1024:
        return None, f"This video is {uploaded.size / 1048576:.0f} MB. Please keep it under {MAX_UPLOAD_MB} MB."
```

**Find:**
```python
    return str(dest), None
```
**Replace with:**
```python
    try:
        return store_file(dest, MIME.get(suffix, "video/mp4")), None
    except Exception as e:
        dest.unlink(missing_ok=True)
        print(f"[JobTok] {e}", flush=True)
        return None, "Could not save the video to storage. Please try again in a moment."
```

---
## Change 12 (EDIT) - save_image
Inside function `save_image` make these 3 changes:

**Find:**
```python
    """Resize + store an image as JPEG. Returns (path, error)."""
```
**Replace with:**
```python
    """Resize + store an image as JPEG. Returns (path_or_url, error)."""
```

**Delete these lines:**
```python
        return str(dest), None
```

**Find this line (keep it) and paste the new lines right AFTER it:**
```python
        return None, "Could not read that image. Please use a JPG or PNG."
```
**New lines to add:**
```python
    try:
        return store_file(dest, "image/jpeg"), None
    except Exception as e:
        dest.unlink(missing_ok=True)
        print(f"[JobTok] {e}", flush=True)
        return None, "Could not save the image to storage. Please try again in a moment."
```

---
## Change 13 (EDIT) - drop_file
Inside function `drop_file` make this change:

**Find:**
```python
    if path:
        Path(path).unlink(missing_ok=True)
```
**Replace with:**
```python
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
```

---
## Change 14 (EDIT) - exists
Inside function `exists` make this change:

**Find:**
```python
    return bool(path) and Path(path).exists()
```
**Replace with:**
```python
    return bool(path) and (is_url(path) or Path(path).exists())
```

---
## Change 15 (EDIT) - avatar_html
Inside function `avatar_html` make this change:

**Find this line (keep it) and paste the new lines right AFTER it:**
```python
    path = p.get("photo_path")
```
**New lines to add:**
```python
    if exists(path) and is_url(path):
        return (f'<img src="{esc(path)}" loading="lazy" '
                f'style="width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;flex:none">')
```

---
## Change 16 (REPLACE) - VIDEO_MAX_W, VIDEO_RATIO, video_player
REPLACE the whole function `video_player` (it starts with `def video_player(path, title="", subtitle="", items=(), badge="", height=540):`) with:  (this block also contains NEW functions/lines - paste all of it)

```python
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
```

---
## Change 17 (EDIT) - auth_screen
Inside function `auth_screen` make these 2 changes:

**Find this line (keep it) and paste the new lines right AFTER it:**
```python
    header()
```
**New lines to add:**
```python
    if st.session_state.get("flash"):
        st.success(st.session_state.pop("flash"))
    if not (db_url() and storage_conf()) and os.path.isdir("/mount/src"):      # running on Streamlit Community Cloud
        st.warning("Storage is not connected: accounts and videos here are deleted whenever this app restarts. "
                   "App owner: set DATABASE_URL and SUPABASE_URL / SUPABASE_SERVICE_KEY in the app Secrets (see README).")
```

**Find this line (keep it) and paste the new lines right AFTER it:**
```python
                    st.session_state.user = user
```
**New lines to add:**
```python
                    remember_login(user["id"])
```

---
## Change 18 (EDIT) - reset_flow
Inside function `reset_flow` make this change:

**Find this line (keep it) and paste the new lines right AFTER it:**
```python
                ex("UPDATE users SET salt=?, pw_hash=? WHERE email=?", (salt, hash_pw(pw, salt), rd["email"]))
```
**New lines to add:**
```python
                ex("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE email=?)", (rd["email"],))
```

---
## Change 19 (EDIT) - verify_step
Inside function `verify_step` make this change:

**Find this line (keep it) and paste the new lines right AFTER it:**
```python
                    st.session_state.user = {"id": uid, "role": su["role"], "name": su["name"], "email": su["email"]}
```
**New lines to add:**
```python
                    remember_login(uid)
```

---
## Change 20 (REPLACE) - posts_page
REPLACE the whole function `posts_page` (it starts with `def posts_page(me, role):`) with:

```python
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
```

---
## Change 21 (EDIT) - messages_page
Inside function `messages_page` make this change:

**Find:**
```python
    rows = q("""SELECT DISTINCT CASE WHEN from_id=? THEN to_id ELSE from_id END AS pid
                FROM messages WHERE from_id=? OR to_id=? ORDER BY id DESC""", (me, me, me))
```
**Replace with:**
```python
    rows = q("""SELECT pid FROM (
                   SELECT CASE WHEN from_id=? THEN to_id ELSE from_id END AS pid, MAX(id) AS last_id
                   FROM messages WHERE from_id=? OR to_id=? GROUP BY CASE WHEN from_id=? THEN to_id ELSE from_id END
                ) t ORDER BY last_id DESC""", (me, me, me, me))
```

---
## Change 22 (ADD) - delete_account, delete_account_ui
ADD this NEW code right AFTER the end of function `completeness` (leave a blank line between):

```python
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
```

---
## Change 23 (EDIT) - logout_button
Inside function `logout_button` make this change:

**Find:**
```python
        st.session_state.clear()
        st.rerun()
```
**Replace with:**
```python
        do_logout()
```

---
## Change 24 (EDIT) - profile_page
Inside function `profile_page` make this change:

**Find this line (keep it) and paste the new lines right AFTER it:**
```python
    logout_button("logout_profile")
```
**New lines to add:**
```python
    delete_account_ui(me)
```

---
## Change 25 (EDIT) - experience_tab
Inside function `experience_tab` make this change:

**Find:**
```python
                ex("INSERT INTO experiences(user_id,role,company,start,end,description) VALUES(?,?,?,?,?,?)",
```
**Replace with:**
```python
                ex('INSERT INTO experiences(user_id,role,company,start,"end",description) VALUES(?,?,?,?,?,?)',
```

---
## Change 26 (EDIT) - main
Inside function `main` make these 4 changes:

**Find this line (keep it) and paste the new lines right AFTER it:**
```python
    user = st.session_state.get("user")
```
**New lines to add:**
```python
    if not user and not st.session_state.get("_cookie_clear"):
        user = restore_login()
        if user:
            st.session_state.user = user
```

**Find this line (keep it) and paste the new lines right AFTER it:**
```python
        auth_screen()
```
**New lines to add:**
```python
        sync_cookie()
```

**Find:**
```python
            st.session_state.clear()
            st.rerun()
```
**Replace with:**
```python
            do_logout()
```

**Find this line (keep it) and paste the new lines right AFTER it:**
```python
    nav_style()
```
**New lines to add:**
```python
    sync_cookie()
```
