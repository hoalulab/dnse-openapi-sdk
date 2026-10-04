#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dnse import DNSEClient


class SmartOtpHandoffClientTest(unittest.TestCase):
    def test_create_smart_otp_handoff_uses_expected_path_version_and_timeout(self):
        client = DNSEClient(
            api_key="key",
            api_secret="secret",
            base_url="https://example.test",
        )
        captured = {}

        def fake_request(method, path, **kwargs):
            captured.update(method=method, path=path, kwargs=kwargs)
            return 200, '{"smartOtp":"123456"}'

        client._request = fake_request

        client.create_smart_otp_handoff()

        self.assertEqual("POST", captured["method"])
        self.assertEqual("/registration/smart-otp/handoff", captured["path"])
        self.assertEqual("2026-01-01", captured["kwargs"]["version"])
        self.assertEqual(330.0, captured["kwargs"]["timeout"].read_timeout)
        self.assertFalse(captured["kwargs"]["dry_run"])


if __name__ == "__main__":
    unittest.main()
