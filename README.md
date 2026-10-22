# JobTok

LinkedIn x TikTok hiring app (Streamlit).

## Run
    pip install -r requirements.txt
    streamlit run app.py

Keep `app.py`, `requirements.txt` and the `.streamlit/` folder together.

## Email verification (sign-up code) - how to make it send REAL emails
New users must enter a 6-digit code that is emailed to them. Codes expire after 10 minutes,
work once, allow 5 wrong tries, can be resent once a minute, max 5 per hour per email.
The same codes power "Forgot password?" on the login screen.

**The app cannot send email until YOU connect an email account.** Until then it runs in
DEMO MODE: no email is sent and the code is shown on screen.

1. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` (same folder, exact name).
2. Keep one block (Gmail or Brevo), put in your real values. Every value in "quotes".
   - Gmail: turn on 2-Step Verification, create an App password
     (https://myaccount.google.com/apppasswords) and use it as SMTP_PASSWORD.
     Your normal Gmail password will NOT work.
3. Test before starting the app:

       python check_email.py yourname@gmail.com

   It checks settings -> server -> secure connection -> login -> sends a test email, and says
   exactly which step fails and how to fix it.
4. Start the app (`streamlit run app.py`) from the folder that contains `.streamlit/`.
   Restart it after any change to secrets.toml.

On a hosting service you can set the same names as environment variables instead
(SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_SECURITY).
Never upload secrets.toml anywhere public. Do not publish the app in demo mode.

Common problems
- "rejected the login" -> wrong password; Gmail needs the App password.
- "Could not reach the mail server" -> wrong SMTP_HOST/SMTP_PORT, or your host blocks the port (try 465 + ssl, or Brevo on 2525).
- Still demo mode -> secrets.toml is in the wrong folder or has a typo; run check_email.py to see what it finds.
- Email in spam -> normal for new senders; use a sender address you own / a service like Brevo.

## Making an Android APK
Streamlit runs on a server, so the APK is a WebView wrapper around your hosted app:
1. Host the app (Streamlit Community Cloud, Render, a VPS, ...) over HTTPS and set the SMTP values there.
   Note: Community Cloud / many hosts wipe local files on restart. For real users, move
   `jobtok.db` and `static/` to persistent storage (a volume, or Postgres + S3).
2. Wrap the URL with a WebView tool (Android Studio WebView, Capacitor, Bubblewrap/TWA, or a no-code site-to-APK builder).
3. Make sure the wrapper allows file uploads (WebView needs `onShowFileChooser`) so users can pick their video and photo.
