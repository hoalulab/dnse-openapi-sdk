#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from dnse import DNSEClient


def main():
    client = DNSEClient(
        api_key="replace-with-api-key",
        api_secret="replace-with-api-secret",
        base_url="https://openapi.dnse.com.vn",
    )

    payload = {
        "takeProfit": {
            "enabled": True,
            "strategy": "PNL_RATE",
            "rate": 0.4,
            "deltaPrice": 162.8,
            "orderMethod": "FASTEST",
            "orderDeltaPrice": 2.0,
        },
        "stopLoss": {
            "enabled": True,
            "strategy": "DELTA_PRICE",
            "rate": 1.0,
            "deltaPrice": 50.0,
            "orderMethod": "DELTA_PRICE",
            "orderDeltaPrice": 10.5,
            "trailingEnabled": True,
        },
    }

    status, body = client.post_position_pnl_configs(
        position_id="replace-with-position-id",
        market_type="DERIVATIVE",
        payload=payload,
        trading_token=os.getenv("DNSE_TRADING_TOKEN"),
        dry_run=False,
    )
    print(status, body)


if __name__ == "__main__":
    main()
