import unittest
from unittest.mock import Mock, patch

import requests

from research.q041 import collect_chains


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self.payload = payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)

    def json(self) -> dict:
        return self.payload


class Q041CollectChainsRetryTests(unittest.TestCase):
    @patch("research.q041.collect_chains.ensure_access_token", return_value="token")
    @patch("research.q041.collect_chains._parse_chain_response")
    @patch("research.q041.collect_chains.requests.get")
    def test_spx_chain_502_retries_with_smaller_request(
        self,
        mock_get: Mock,
        mock_parse: Mock,
        _mock_token: Mock,
    ) -> None:
        mock_get.side_effect = [
            _Response(502),
            _Response(200, {"ok": True}),
        ]
        mock_parse.side_effect = [
            [{"expiry": "2026-06-19", "strike": 7000}],
            [{"expiry": "2026-06-19", "strike": 7000}],
        ]

        calls, puts = collect_chains._fetch_full_chain("SPX")

        self.assertEqual(len(calls), 1)
        self.assertEqual(len(puts), 1)
        self.assertEqual(mock_get.call_count, 2)
        first_params = mock_get.call_args_list[0].kwargs["params"]
        second_params = mock_get.call_args_list[1].kwargs["params"]
        self.assertEqual(first_params["symbol"], "$SPX")
        self.assertEqual(first_params["strikeCount"], 160)
        self.assertEqual(second_params["strikeCount"], 120)


if __name__ == "__main__":
    unittest.main()
