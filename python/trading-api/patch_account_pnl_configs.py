#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from dnse import DNSEClient


def main():
    client = DNSEClient(
        api_key=os.getenv("DNSE_API_KEY"),
        api_secret=os.getenv("DNSE_API_SECRET"),
        base_url="https://openapi.dnse.com.vn",
    )
    payload = {
        "takeProfit": {
            "enabled": True,
            "strategy": "PNL_RATE",
            "rate": 0.4,
            "orderMethod": "FASTEST",
            "orderDeltaPrice": 2.0,
        },
        "stopLoss": {
            "enabled": True,
            "strategy": "DELTA_PRICE",
            "rate": -0.1,
            "orderMethod": "DELTA_PRICE",
            "orderDeltaPrice": 10.5,
            "trailingEnabled": True,
        },
    }
    status, body = client.patch_account_pnl_configs(
        account_no=os.getenv("DNSE_ACCOUNT_NO"),
        market_type="DERIVATIVE",
        payload=payload,
        trading_token=os.getenv("DNSE_TRADING_TOKEN"),
        dry_run=False,
    )
    print(status, body)


if __name__ == "__main__":
    main()
