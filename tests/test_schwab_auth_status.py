import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import schwab.auth as auth


class SchwabAuthStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.token_file = Path(self.tmp.name) / "schwab_token.json"
        self.env = patch.dict(
            os.environ,
            {
                "SCHWAB_CLIENT_ID": "client",
                "SCHWAB_CLIENT_SECRET": "secret",
            },
        )
        self.token_patch = patch.object(auth, "TOKEN_FILE", self.token_file)
        self.env.start()
        self.token_patch.start()

    def tearDown(self) -> None:
        self.token_patch.stop()
        self.env.stop()
        self.tmp.cleanup()

    def _write_token(self, access_delta: timedelta, refresh_delta: timedelta) -> None:
        now = datetime.now(ZoneInfo("America/New_York"))
        self.token_file.write_text(json.dumps({
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_at": (now + access_delta).isoformat(),
            "refresh_expires_at": (now + refresh_delta).isoformat(),
        }))

    def test_expired_access_with_valid_refresh_does_not_require_reauth(self) -> None:
        self._write_token(timedelta(minutes=-1), timedelta(days=3))

        status = auth.token_status()

        self.assertFalse(status["authenticated"])
        self.assertFalse(status["access_token_valid"])
        self.assertTrue(status["refresh_token_valid"])
        self.assertFalse(status["requires_reauth"])

    def test_expired_refresh_requires_reauth(self) -> None:
        self._write_token(timedelta(minutes=-1), timedelta(minutes=-1))

        status = auth.token_status()

        self.assertFalse(status["authenticated"])
        self.assertFalse(status["refresh_token_valid"])
        self.assertTrue(status["requires_reauth"])


if __name__ == "__main__":
    unittest.main()
