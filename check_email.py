"""
Test your JobTok email settings BEFORE running the app.

    python check_email.py you@example.com

It reads the same settings as the app (environment variables or .streamlit/secrets.toml),
walks through each step (settings -> server -> secure connection -> login -> send) and tells you
exactly which step fails and how to fix it. A test email with a sample code is sent to the address you give.
"""
import os
import re
import smtplib
import socket
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

KEYS = ["SMTP_HOST", "SMTP_PORT", "SMTP_SECURITY", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"]


def load_secrets():
    """Return (settings dict, path of the file used or None)."""
    here = Path(__file__).resolve().parent
    for p in (Path.cwd() / ".streamlit" / "secrets.toml", here / ".streamlit" / "secrets.toml",
              Path.home() / ".streamlit" / "secrets.toml"):
        if not p.is_file():
            continue
        try:
            try:
                import tomllib
            except ImportError:                     # Python < 3.11
                import tomli as tomllib             # type: ignore
            data = tomllib.loads(p.read_text(encoding="utf-8"))
        except ImportError:                         # tiny fallback parser:  KEY = "value"
            data = {}
            for line in p.read_text(encoding="utf-8").splitlines():
                m = re.match(r'\s*([A-Za-z_]+)\s*=\s*"?([^"#]*)"?\s*(#.*)?$', line)
                if m:
                    data[m.group(1)] = m.group(2).strip()
        except Exception as e:
            print(f"✖ Could not read {p}: {e}\n  The file has a syntax error. Every value must be in quotes, e.g. SMTP_USER = \"me@gmail.com\"")
            sys.exit(1)
        flat = dict(data)
        for tbl in ("smtp", "SMTP"):
            if isinstance(data.get(tbl), dict):
                for k, v in data[tbl].items():
                    flat.setdefault(k if k.startswith("SMTP_") else "SMTP_" + k.upper(), v)
        return flat, p
    return {}, None


def main():
    to = sys.argv[1] if len(sys.argv) > 1 else None
    file_cfg, used = load_secrets()
    cfg = {k: os.environ.get(k) or file_cfg.get(k) for k in KEYS}

    print("1) Settings")
    if used:
        print(f"   secrets file : {used}")
    else:
        print("   secrets file : NOT FOUND (looked in ./.streamlit, next to this script, and ~/.streamlit)")
    for k in KEYS:
        v = cfg[k]
        shown = "(not set)" if not v else ("*" * len(str(v).replace(" ", "")) if k == "SMTP_PASSWORD" else v)
        print(f"   {k:14}: {shown}")
    if not (cfg["SMTP_HOST"] and cfg["SMTP_USER"] and cfg["SMTP_PASSWORD"]):
        print("\n✖ SMTP_HOST, SMTP_USER and SMTP_PASSWORD are required. Copy .streamlit/secrets.toml.example to "
              ".streamlit/secrets.toml, fill it in and run this again.\n  Until then the app is in DEMO MODE and sends no email.")
        sys.exit(1)

    host, user = str(cfg["SMTP_HOST"]).strip(), str(cfg["SMTP_USER"]).strip()
    pw = str(cfg["SMTP_PASSWORD"]).replace(" ", "")
    port = int(cfg["SMTP_PORT"] or 587)
    sec = str(cfg["SMTP_SECURITY"] or ("ssl" if port == 465 else "starttls")).lower()
    sender = cfg["SMTP_FROM"] or user
    to = to or user

    print(f"\n2) Reaching {host}:{port} ...")
    try:
        socket.create_connection((host, port), timeout=15).close()
        print("   ✔ server reachable")
    except socket.gaierror:
        print(f"   ✖ The name '{host}' does not exist. Check SMTP_HOST for typos (Gmail: smtp.gmail.com).")
        sys.exit(1)
    except OSError as e:
        print(f"   ✖ Cannot connect ({e}). Wrong SMTP_PORT, or your network/host blocks it.\n"
              "     Try 465 + SMTP_SECURITY=ssl, or 2525 (Brevo/Mailgun), or run from another network.")
        sys.exit(1)

    print(f"3) Secure connection ({sec}) and login as {user} ...")
    try:
        if sec == "ssl":
            server = smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20)
        else:
            server = smtplib.SMTP(host, port, timeout=20)
            if sec == "starttls":
                server.starttls(context=ssl.create_default_context())
        server.login(user, pw)
        print("   ✔ logged in")
    except smtplib.SMTPAuthenticationError as e:
        print(f"   ✖ Login rejected ({e.smtp_code}). The user or password is wrong.\n"
              "     Gmail: you MUST use an App Password (16 letters) from https://myaccount.google.com/apppasswords\n"
              "     (2-Step Verification has to be on). Your normal Gmail password will never work.")
        sys.exit(1)
    except (ssl.SSLError, smtplib.SMTPNotSupportedError, smtplib.SMTPServerDisconnected) as e:
        print(f"   ✖ Security mismatch ({e}). Use port 587 + SMTP_SECURITY=starttls, or port 465 + SMTP_SECURITY=ssl.")
        sys.exit(1)
    except Exception as e:
        print(f"   ✖ {type(e).__name__}: {e}")
        sys.exit(1)

    print(f"4) Sending a test email to {to} ...")
    msg = EmailMessage()
    msg["Subject"] = "123456 is your JobTok verification code (test)"
    msg["From"] = sender
    msg["To"] = to
    msg.set_content("This is a test from JobTok. If you can read this, real verification emails will work.\n\nSample code: 123456")
    try:
        with server:
            server.send_message(msg)
        print(f"   ✔ sent! Check the inbox of {to} (and the spam folder).")
        print("\n✔ Everything works. Restart the app and sign up with a real email.")
    except smtplib.SMTPRecipientsRefused:
        print("   ✖ The server refused the recipient address.")
        sys.exit(1)
    except smtplib.SMTPSenderRefused:
        print(f"   ✖ The server refused the sender '{sender}'. Set SMTP_FROM to your own verified address.")
        sys.exit(1)
    except Exception as e:
        print(f"   ✖ {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
