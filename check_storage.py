"""
Test your permanent storage settings BEFORE (or after) deploying.

    python check_storage.py

Checks, step by step, the two things that keep accounts and videos from disappearing:
  1) DATABASE_URL  -> a Postgres database (Supabase) that stores accounts, posts, messages ...
  2) SUPABASE_URL + SUPABASE_SERVICE_KEY -> file storage for videos and photos
Settings are read from environment variables or .streamlit/secrets.toml (same as the app).
"""
import os
import sys
import uuid

from check_email import load_secrets          # same secrets.toml reader as the email checker

KEYS = ["DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "SUPABASE_BUCKET"]


def main():
    file_cfg, used = load_secrets()
    cfg = {k: os.environ.get(k) or file_cfg.get(k) for k in KEYS}
    print("1) Settings   (secrets file:", used or "NOT FOUND", ")")
    for k in KEYS:
        v = cfg[k]
        shown = "(not set)" if not v else (v[:18] + "…" if k != "SUPABASE_BUCKET" else v)
        print(f"   {k:21}: {shown}")
    bad = False

    print("\n2) Database")
    if not cfg["DATABASE_URL"]:
        print("   ✖ DATABASE_URL not set -> the app uses a local file that is ERASED on cloud hosts. Accounts will vanish.")
        bad = True
    else:
        try:
            import psycopg2
        except ImportError:
            print("   ✖ psycopg2 is not installed: pip install psycopg2-binary")
            sys.exit(1)
        try:
            conn = psycopg2.connect(cfg["DATABASE_URL"], connect_timeout=15)
            cur = conn.cursor()
            cur.execute("select version()")
            print("   ✔ connected:", cur.fetchone()[0][:60])
            cur.execute("select count(*) from information_schema.tables where table_name='users'")
            print("   ✔ JobTok tables:", "already created" if cur.fetchone()[0] else "not created yet (the app creates them on first start)")
            conn.close()
        except Exception as e:
            msg = str(e).strip().splitlines()[0]
            print(f"   ✖ cannot connect: {msg}")
            if "password authentication" in msg:
                print("     Wrong password in DATABASE_URL (special characters like @ : / must be URL-encoded).")
            elif "Network is unreachable" in msg or "could not translate" in msg:
                print("     Use the *Session pooler* connection string from Supabase (the 'direct' one is IPv6-only and cloud hosts cannot reach it).")
            bad = True

    print("\n3) File storage")
    if not (cfg["SUPABASE_URL"] and cfg["SUPABASE_SERVICE_KEY"]):
        print("   ✖ SUPABASE_URL / SUPABASE_SERVICE_KEY not set -> videos and photos are ERASED when the app restarts.")
        bad = True
    else:
        import requests

        url, key, bucket = cfg["SUPABASE_URL"].rstrip("/"), cfg["SUPABASE_SERVICE_KEY"], cfg["SUPABASE_BUCKET"] or "jobtok"
        h = {"Authorization": f"Bearer {key}", "apikey": key}
        try:
            r = requests.post(f"{url}/storage/v1/bucket", json={"id": bucket, "name": bucket, "public": True}, headers=h, timeout=20)
            if r.status_code in (200, 201):
                print(f"   ✔ bucket '{bucket}' created (public)")
            elif r.status_code in (400, 409):
                print(f"   ✔ bucket '{bucket}' already exists")
            elif r.status_code in (401, 403):
                print("   ✖ key rejected (401/403). Use the *service_role* / secret key from Project Settings > API (not the anon/publishable key).")
                print("     If you use the new 'sb_secret_…' key and still get this, use the legacy service_role key instead.")
                sys.exit(1)
            else:
                print(f"   ✖ unexpected answer {r.status_code}: {r.text[:150]}")
                bad = True
            name = f"check_{uuid.uuid4().hex[:8]}.txt"
            up = requests.post(f"{url}/storage/v1/object/{bucket}/{name}", data=b"hello jobtok", timeout=30,
                               headers={**h, "Content-Type": "text/plain"})
            print("   ✔ upload works" if up.status_code < 300 else f"   ✖ upload failed {up.status_code}: {up.text[:150]}")
            if up.status_code < 300:
                get = requests.get(f"{url}/storage/v1/object/public/{bucket}/{name}", timeout=20)
                print("   ✔ public link works (videos can be streamed)" if get.status_code == 200 and get.content == b"hello jobtok"
                      else f"   ✖ public link failed ({get.status_code}) - make sure the bucket is PUBLIC")
                d = requests.delete(f"{url}/storage/v1/object/{bucket}/{name}", headers=h, timeout=20)
                print("   ✔ delete works" if d.status_code < 300 else f"   ✖ delete failed {d.status_code}")
        except Exception as e:
            print(f"   ✖ cannot reach {url}: {type(e).__name__}. Check SUPABASE_URL (looks like https://abcd1234.supabase.co).")
            bad = True

    print("\n" + ("✖ Fix the items above, then run this again." if bad else "✔ All good: accounts and videos will now stay until users delete them."))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
