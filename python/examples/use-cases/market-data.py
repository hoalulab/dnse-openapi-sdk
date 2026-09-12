#!/usr/bin/env python3
"""Use case: security info and price limits for a list of symbols. No OTP required.

Ported from dnse-py to drive THIS project's ``DNSEClient`` — signing is handled
inside the client (see ``dnse/api/common.py``).

Config via env vars: DNSE_API_KEY, DNSE_API_SECRET, DNSE_BASE_URL
Run: python examples/use-cases/market-data.py
"""
import json
import os
import sys

# Import the local SDK (three levels up: examples/use-cases -> examples -> python/)
_EXAMPLES_DIR = os.path.dirname(os.path.dirname(__file__))  # examples/
sys.path.insert(0, os.path.dirname(_EXAMPLES_DIR))          # python/  (for `dnse`)
sys.path.insert(0, _EXAMPLES_DIR)                           # examples/ (helpers)

from dnse import DNSEClient
from env_util import load_dotenv
from log_util import log

load_dotenv()

SYMBOLS = ["HPG", "VIC", "VNM", "SSI", "TCB"]


def main():
    client = DNSEClient(
        api_key=os.environ.get("DNSE_API_KEY", "replace-with-api-key"),
        api_secret=os.environ.get("DNSE_API_SECRET", "replace-with-api-secret"),
        base_url=os.environ.get("DNSE_BASE_URL", "https://openapi.dnse.com.vn"),
        api_version=os.environ.get("DNSE_API_VERSION", "2026-07-23"),
    )

    log(f"{'Mã':<8} {'Trần':>10} {'Sàn':>10} {'TC':>10}")
    log("-" * 42)
    for sym in SYMBOLS:
        status, body = client.get_security_definition(sym)
        if not status or status >= 300:
            log(f"{sym:<8} lỗi [{status}]")
            continue
        data = json.loads(body)
        sec = (data if isinstance(data, list) else [data])[0]  # first board entry
        log(
            f"{sym:<8} {sec['ceilingPrice']:>10} {sec['floorPrice']:>10} {sec['basicPrice']:>10}"
        )


if __name__ == "__main__":
    main()
