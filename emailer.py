"""
emailer.py

Sends a digest email of new high-fit jobs using Gmail.

SETUP (one time) - getting a Gmail App Password:
  1. Your Google account must have 2-Step Verification ON.
     (myaccount.google.com -> Security -> 2-Step Verification)
  2. Go to:  myaccount.google.com/apppasswords
  3. Create a new app password (name it e.g. "job-alerts").
     Google shows you a 16-character code like: abcd efgh ijkl mnop
  4. This code is NOT your real Gmail password. It only lets this script send
     mail, and you can revoke it anytime from the same page.

Then add two lines to your ".env" file (the same file with your API key), so it
looks like this (no quotes, no spaces around =):

    ANTHROPIC_API_KEY=sk-ant-...
    GMAIL_ADDRESS=yourname@gmail.com
    GMAIL_APP_PASSWORD=abcdefghijklmnop

The script reads them from .env - the password never lives in code.
You send the email to yourself (from and to are the same address by default).
"""

import os
import smtplib
from email.message import EmailMessage

# Load the .env file so GMAIL_ADDRESS and GMAIL_APP_PASSWORD are available.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def send_job_digest(jobs):
    """Send an email listing the given jobs. `jobs` is a list of dicts with
    keys: company, title, location, ai_score, ai_reason, url.

    Returns True on success, False if not configured or on error.
    """
    sender = os.environ.get("GMAIL_ADDRESS")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not sender or not app_password:
        print("Email not configured. Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD.")
        print("See the setup notes at the top of emailer.py.")
        return False

    if not jobs:
        print("No new high-fit jobs to email.")
        return False

    # Build a clean, readable body. Plain text - simple and reliable.
    lines = [f"{len(jobs)} new job(s) worth a look:\n"]
    for job in jobs:
        lines.append(f"[{job['ai_score']}/100] {job['company']} - {job['title']}")
        lines.append(f"   Location: {job['location']}")
        lines.append(f"   Why: {job['ai_reason']}")
        lines.append(f"   Apply: {job['url']}")
        lines.append("")

    body = "\n".join(lines)

    message = EmailMessage()
    message["Subject"] = f"Job alerts: {len(jobs)} new match(es)"
    message["From"] = sender
    message["To"] = sender  # send to yourself
    message.set_content(body)

    try:
        # Gmail's SMTP over SSL on port 465.
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, app_password)
            server.send_message(message)
        print(f"Email sent to {sender} with {len(jobs)} job(s).")
        return True
    except smtplib.SMTPAuthenticationError:
        print("Gmail rejected the login. Check that:")
        print("  - 2-Step Verification is ON")
        print("  - you used an App Password (not your normal password)")
        return False
    except Exception as error:
        print(f"Could not send email: {error}")
        return False
