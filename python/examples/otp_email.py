#!/usr/bin/env python3
"""Automatically read the DNSE OTP from an email inbox over IMAP.

Standard-library only (``imaplib`` + ``email``) — no extra dependencies.

Typical use inside an example::

    import time
    from otp_email import resolve_otp

    requested_at = time.time()
    client.send_email_otp()
    otp = resolve_otp(after_ts=requested_at)   # auto-fetch, or prompt if unconfigured

Configuration (environment variables):

    OTP_EMAIL_USER       IMAP username (the mailbox that receives the OTP)
    OTP_EMAIL_PASSWORD   IMAP password / app password (see notes below)
    OTP_IMAP_HOST        IMAP server host        (default: imap.gmail.com)
    OTP_IMAP_PORT        IMAP SSL port           (default: 993)
    OTP_MAILBOX          Mailbox to search       (default: INBOX)
    OTP_FROM             Only match senders containing this substring (default: dnse)
    OTP_REGEX            Regex with one capture group for the code
                         (default: a 6-digit run, "(?<!\\d)(\\d{6})(?!\\d)")
    OTP_TIMEOUT          Seconds to poll for the email (default: 120)
    OTP_POLL_INTERVAL    Seconds between polls (default: 3)

If OTP_EMAIL_USER / OTP_EMAIL_PASSWORD are not set, ``resolve_otp`` falls back to
a manual ``input()`` prompt, so examples keep working without any email config.

Gmail note: enable IMAP (Settings → Forwarding and POP/IMAP) and create an
App Password (Google Account → Security → 2-Step Verification → App passwords);
use that 16-char app password as OTP_EMAIL_PASSWORD, not your normal password.
"""
import email
import imaplib
import os
import re
import time
from email.header import decode_header
from email.utils import parsedate_to_datetime
from env_util import load_dotenv
from log_util import log

DEFAULT_REGEX = r"\b(\d{6})\b"  # 6-digit run with word boundaries (avoids digits inside IDs like 064C950519)


load_dotenv()


def _getenv(name, default=None):
    """Read an env var, tolerating exact / UPPER / lower case spellings."""
    for key in (name, name.upper(), name.lower()):
        if os.environ.get(key):
            return os.environ[key]
    return default


def _decode_header(value):
    """Decode a possibly MIME-encoded header into a plain string."""
    if not value:
        return ""
    parts = []
    for text, enc in decode_header(value):
        if isinstance(text, bytes):
            parts.append(text.decode(enc or "utf-8", "ignore"))
        else:
            parts.append(text)
    return "".join(parts)


def _message_text(msg):
    """Concatenate subject + all text/plain and text/html parts of a message."""
    chunks = [_decode_header(msg.get("Subject", ""))]
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        if part.get_content_type() in ("text/plain", "text/html"):
            payload = part.get_payload(decode=True)
            if payload:
                chunks.append(payload.decode(part.get_content_charset() or "utf-8", "ignore"))
    return "\n".join(chunks)


def _message_time(msg):
    """Return the message Date as an epoch float, or None if unparseable."""
    try:
        return parsedate_to_datetime(msg.get("Date")).timestamp()
    except (TypeError, ValueError):
        return None


def fetch_otp(after_ts, *, timeout=None, poll_interval=None):
    """Poll the configured IMAP inbox for a fresh OTP and return the code.

    Args:
        after_ts: Only accept messages dated at/after this epoch (with a small
            buffer). Pass the timestamp captured just before send_email_otp().
        timeout: Max seconds to poll (default OTP_TIMEOUT / 120).
        poll_interval: Seconds between polls (default OTP_POLL_INTERVAL / 3).

    Returns:
        The OTP string, or None if none arrived within the timeout.

    Raises:
        RuntimeError: If OTP_EMAIL_USER / OTP_EMAIL_PASSWORD are not configured.
    """
    user = _getenv("OTP_EMAIL_USER")
    password = _getenv("OTP_EMAIL_PASSWORD")
    if not user or not password:
        raise RuntimeError("OTP_EMAIL_USER / OTP_EMAIL_PASSWORD not set")

    host = _getenv("OTP_IMAP_HOST", "imap.gmail.com")
    port = int(_getenv("OTP_IMAP_PORT", "993"))
    mailbox = _getenv("OTP_MAILBOX", "INBOX")
    sender = _getenv("OTP_FROM", "dnse")
    pattern = _getenv("OTP_REGEX", DEFAULT_REGEX)
    timeout = float(_getenv("OTP_TIMEOUT", "120")) if timeout is None else timeout
    poll_interval = (
        float(_getenv("OTP_POLL_INTERVAL", "3")) if poll_interval is None else poll_interval
    )
    log(f"Tự lấy OTP: {user} @ {host}:{port} (hộp thư={mailbox}, người gửi~{sender!r})")
    cutoff = after_ts - 120  # buffer: IMAP dates and local clock may drift

    imap = imaplib.IMAP4_SSL(host, port)
    imap.login(user, password)
    try:
        deadline = time.time() + timeout
        while True:
            imap.select(mailbox)
            criteria = ["UNSEEN"]
            if sender:
                criteria += ["FROM", sender]
            typ, data = imap.search(None, *criteria)
            ids = data[0].split() if typ == "OK" and data and data[0] else []

            # Newest first; only look at the last handful of unread messages.
            for num in reversed(ids[-10:]):
                typ, msg_data = imap.fetch(num, "(RFC822)")
                if typ != "OK" or not msg_data or not msg_data[0]:
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                msg_ts = _message_time(msg)
                if msg_ts is not None and msg_ts < cutoff:
                    continue  # stale email from a previous request
                match = re.search(pattern, _message_text(msg))
                if match:
                    return match.group(1)

            if time.time() >= deadline:
                return None
            time.sleep(poll_interval)
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def is_configured():
    """True if IMAP auto-fetch env vars are present."""
    return bool(_getenv("OTP_EMAIL_USER") and _getenv("OTP_EMAIL_PASSWORD"))


def resolve_otp(after_ts=None, *, prompt="Enter OTP from email: "):
    """Auto-fetch the OTP from email if configured, else prompt the user.

    Args:
        after_ts: Timestamp captured just before requesting the OTP (used to
            ignore older OTP emails). Defaults to ~5s ago.
        prompt: Fallback input() prompt when auto-fetch is unavailable.

    Returns:
        The OTP string (may be empty if the user submits nothing at the prompt).
    """
    if is_configured():
        log("Đang chờ email OTP...")
        try:
            code = fetch_otp(after_ts if after_ts is not None else time.time() - 5)
        except Exception as exc:  # IMAP login/connection error, etc.
            log(f"Lấy OTP qua email thất bại ({type(exc).__name__}: {exc}); nhập tay.")
            code = None
        if code:
            log(f"Đã tự lấy OTP từ email: {code}")
            return code
        log("Không lấy được OTP kịp thời; chuyển sang nhập tay.")
    else:
        # Email auto-fetch not configured — this is fine, just enter the OTP by hand.
        # (To enable auto-fetch later, set OTP_EMAIL_USER / OTP_EMAIL_PASSWORD in examples/.env)
        pass
    return input(prompt).strip()
