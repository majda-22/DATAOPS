"""Verify bucket availability and a Python-to-MinIO object round trip."""

import hashlib
import json
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.config import Config
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    settings = dotenv_values(ROOT / ".env")
    username = settings.get("MINIO_ROOT_USER")
    password = settings.get("MINIO_ROOT_PASSWORD")
    if not username or not password:
        raise RuntimeError("Set MINIO_ROOT_USER and MINIO_ROOT_PASSWORD in .env")

    port = settings.get("MINIO_API_PORT") or "19000"
    endpoint = f"http://127.0.0.1:{port}"

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=username,
        aws_secret_access_key=password,
        region_name="us-east-1",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=10,
            retries={"max_attempts": 2},
        ),
    )

    try:
        expected = {"bronze", "silver", "gold", "quarantine"}
        actual = {bucket["Name"] for bucket in client.list_buckets()["Buckets"]}
        missing = expected - actual
        if missing:
            raise RuntimeError(f"Missing buckets: {sorted(missing)}")

        key = f"_smoke/{uuid4().hex}.json"
        payload = json.dumps(
            {"project": "DataOps Detective", "test": "object-round-trip"},
            sort_keys=True,
        ).encode("utf-8")

        client.put_object(
            Bucket="bronze",
            Key=key,
            Body=payload,
            ContentType="application/json",
        )

        # Remove only this test's unique object, even if verification fails.
        try:
            response = client.get_object(Bucket="bronze", Key=key)
            body = response["Body"]
            try:
                received = body.read()
            finally:
                body.close()

            if received != payload:
                raise RuntimeError("Downloaded bytes differ from uploaded bytes")
        finally:
            client.delete_object(Bucket="bronze", Key=key)

        print(
            json.dumps(
                {
                    "status": "success",
                    "endpoint": endpoint,
                    "buckets": sorted(expected),
                    "bytes_verified": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "test_object_deleted": True,
                },
                indent=2,
            )
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
