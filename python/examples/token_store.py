#!/usr/bin/env python3
"""Cache the DNSE trading token on disk and reuse it until it expires.

The trading token is obtained via the OTP flow and stays valid for ~8 hours.
This module persists it so you only do the OTP dance once per validity window,
instead of every app start.

High-level API::

    from token_store import ensure_trading_token
    token = ensure_trading_token(rest)   # reuses cache, or runs OTP + caches

Low-level API: load_token / save_token / clear_token.

The cache file (default: examples/.trading_token.json, override with
DNSE_TOKEN_CACHE) is written with 0600 perms and is gitignored. The token is
tied to a fingerprint of the API key, so changing credentials forces a refresh.
"""
import hashlib
import json
import os
import time

from otp_email import resolve_otp  # importing also auto-loads examples/.env
from log_util import log

TTL_SECONDS = 8 * 3600      # DNSE trading token lifetime
REFRESH_MARGIN = 120        # refresh if less than this many seconds remain


def _cache_path():
    return os.environ.get(
        "DNSE_TOKEN_CACHE",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".trading_token.json"),
    )


def _fingerlog(api_key):
    return hashlib.sha256((api_key or "").encode("utf-8")).hexdigest()[:16]


def load_token(api_key, *, ttl=TTL_SECONDS):
    """Return a still-valid cached token for this api_key, or None."""
    try:
        with open(_cache_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if data.get("fingerprint") != _fingerlog(api_key):
        return None  # cache belongs to different credentials
    remaining = data.get("issued_at", 0) + ttl - time.time()
    if remaining <= REFRESH_MARGIN:
        return None  # expired (or about to)
    return data.get("trading_token"), remaining


def save_token(api_key, token, *, ttl=TTL_SECONDS):
    """Persist the token with an issue timestamp (0600 perms)."""
    path = _cache_path()
    payload = {
        "fingerprint": _fingerlog(api_key),
        "trading_token": token,
        "issued_at": time.time(),
        "ttl": ttl,
    }
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return path


def clear_token():
    """Delete the cached token (call this when the server rejects it)."""
    try:
        os.remove(_cache_path())
    except OSError:
        pass


def ensure_trading_token(rest, *, api_key=None, otp_type="email_otp", force=False):
    """Return a valid trading token, reusing the cache when possible.

    On a cache miss (missing/expired/forced) this runs the OTP flow:
    send_email_otp() -> resolve_otp() (auto from email or manual) ->
    create_trading_token(), then caches the result.

    Args:
        rest: A DNSEClient instance.
        api_key: API key to key the cache on (defaults to DNSE_API_KEY env).
        otp_type: OTP type for create_trading_token ("email_otp" | "smart_otp").
        force: Ignore any cached token and re-authenticate.

    Returns:
        The trading token string.
    """
    api_key = api_key if api_key is not None else os.environ.get("DNSE_API_KEY", "")

    if not force:
        cached = load_token(api_key)
        if cached:
            token, remaining = cached
            log(f"Dùng lại trading token đã lưu (còn {remaining / 3600:.1f}h).")
            return token

    requested_at = time.time()
    rest.send_email_otp()
    otp = resolve_otp(after_ts=requested_at)
    status, body = rest.create_trading_token(otp_type=otp_type, passcode=otp)
    if not status or status >= 300:
        raise SystemExit(f"create_trading_token() lỗi [{status}]: {body}")
    token = json.loads(body)["tradingToken"]
    save_token(api_key, token)
    log("Đã lấy trading token mới và lưu lại (hiệu lực ~8h).")
    return token
