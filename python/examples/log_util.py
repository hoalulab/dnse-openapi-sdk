#!/usr/bin/env python3
"""Tiny logging helper: print with the current time prefixed.

Standard library only (`datetime`) — no external logging dependency.
The timestamp is Vietnam local time (UTC+7).
"""
from datetime import datetime, timedelta, timezone

_VN_TZ = timezone(timedelta(hours=7))


def now_str():
    """Current time as 'YYYY-MM-DD HH:MM:SS,mmm' (VN, UTC+7) — matches the WS logs."""
    dt = datetime.now(_VN_TZ)
    return dt.strftime("%Y-%m-%d %H:%M:%S") + f",{dt.microsecond // 1000:03d}"


def log(*args, **kwargs):
    """Like print(), but prefixed with the current [HH:MM:SS] time."""
    print(f"[{now_str()}]", *args, **kwargs)
