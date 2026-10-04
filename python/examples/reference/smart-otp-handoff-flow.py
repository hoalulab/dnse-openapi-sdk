#!/usr/bin/env python3
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dnse import DNSEClient


def main():
    client = DNSEClient(
        api_key=os.getenv("DNSE_API_KEY"),
        api_secret=os.getenv("DNSE_API_SECRET"),
        base_url="https://openapi.dnse.com.vn",
    )

    status, body = client.create_smart_otp_handoff()
    if status != 200:
        print(status, body)
        return

    smart_otp = json.loads(body)["smartOtp"]
    status, body = client.create_trading_token(
        otp_type="smart_otp",
        passcode=smart_otp,
    )
    print(status, body)


if __name__ == "__main__":
    main()
