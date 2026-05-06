"""T4 Massive Flat Files download test — official boto3 method."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

ACCESS_KEY = os.environ["MASSIVE_S3_ACCESS_KEY_ID"]
SECRET_KEY = os.environ["MASSIVE_S3_SECRET_ACCESS_KEY"]
BUCKET = os.environ.get("MASSIVE_S3_BUCKET", "flatfiles")
ENDPOINT = os.environ.get("MASSIVE_S3_ENDPOINT", "https://files.massive.com")

TEST_KEY = "us_options_opra/day_aggs_v1/2022/05/2022-05-06.csv.gz"
OUT_PATH = REPO_ROOT / "data" / "q041_test_download.csv.gz"

print(f"Endpoint : {ENDPOINT}")
print(f"Bucket   : {BUCKET}")
print(f"Key      : {TEST_KEY}")
print(f"Out      : {OUT_PATH}")
print()

session = boto3.Session(
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)

s3 = session.client(
    "s3",
    endpoint_url=ENDPOINT,
    config=Config(signature_version="s3v4"),
)

print(f"Downloading {TEST_KEY} ...")
try:
    s3.download_file(BUCKET, TEST_KEY, str(OUT_PATH))
    size = OUT_PATH.stat().st_size
    print(f"SUCCESS — {size:,} bytes saved to {OUT_PATH}")
except Exception as exc:
    print(f"FAIL — {exc}")
    sys.exit(1)
