#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dnse import DNSEClient


class DNSEClientTest(unittest.TestCase):
    def test_get_loans_builds_expected_request(self):
        client = DNSEClient(
            api_key="key",
            api_secret="secret",
            base_url="https://example.test",
        )
        captured = {}

        def fake_request(method, path, query=None, **kwargs):
            captured.update(method=method, path=path, query=query, kwargs=kwargs)
            return 200, "{}"

        client._request = fake_request

        client.get_loans(
            account_no="0001179019",
            market_type="STOCK",
            disbursement_from="2026-06-01",
            disbursement_to="2026-07-31",
            due_date_from="2026-09-01",
            due_date_to="2026-12-31",
            position_id=9638,
            page_index=2,
            page_size=25,
        )

        self.assertEqual("GET", captured["method"])
        self.assertEqual("/accounts/0001179019/loans", captured["path"])
        self.assertEqual(
            {
                "marketType": "STOCK",
                "disbursementFrom": "2026-06-01",
                "disbursementTo": "2026-07-31",
                "dueDateFrom": "2026-09-01",
                "dueDateTo": "2026-12-31",
                "positionId": 9638,
                "pageIndex": 2,
                "pageSize": 25,
            },
            captured["query"],
        )
        self.assertEqual({"dry_run": False}, captured["kwargs"])


if __name__ == "__main__":
    unittest.main()
