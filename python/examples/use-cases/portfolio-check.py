#!/usr/bin/env python3
"""Use case: list accounts and their balances. No OTP required.

Ported from dnse-py to drive THIS project's ``DNSEClient`` — signing is handled
inside the client (see ``dnse/api/common.py``).

Config via env vars: DNSE_API_KEY, DNSE_API_SECRET, DNSE_BASE_URL
Run: python examples/use-cases/portfolio-check.py
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


def main():
    client = DNSEClient(
        api_key=os.environ.get("DNSE_API_KEY", "replace-with-api-key"),
        api_secret=os.environ.get("DNSE_API_SECRET", "replace-with-api-secret"),
        base_url=os.environ.get("DNSE_BASE_URL", "https://openapi.dnse.com.vn"),
        api_version=os.environ.get("DNSE_API_VERSION", "2026-07-23"),
    )

    status, body = client.get_accounts()
    if not status or status >= 300:
        raise SystemExit(f"get_accounts() lỗi [{status}]: {body}")
    data = json.loads(body)

    log(f"Mã nhà đầu tư (investorId): {data.get('investorId')}")
    for acct in data.get("accounts", []):
        acct_no = acct["id"]
        b_status, b_body = client.get_balances(acct_no)
        log(
            f"\nTiểu khoản {acct_no} "
            f"(deal={acct.get('dealAccount')} phái sinh={acct.get('derivativeAccount')}):"
        )
        log(f"  Số dư [{b_status}]: {b_body}")


if __name__ == "__main__":
    main()
