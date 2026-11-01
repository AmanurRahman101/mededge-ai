"""Private S3-compatible storage for sensitive record files."""

import re
from typing import Any


class StorageError(RuntimeError):
    pass


class PrivateObjectStorage:
    def __init__(self, client: Any, bucket: str):
        if not bucket:
            raise ValueError("A private storage bucket is required")
        self.client = client
        self.bucket = bucket

    @staticmethod
    def key(run_id: str, name: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", run_id):
            raise ValueError("Invalid record identifier")
        if name not in {"original", "audio", "redacted", "overlay", "table"}:
            raise ValueError("Invalid file type")
        return f"records/{run_id}/{name}"

    def put(self, run_id: str, name: str, data: bytes, content_type: str) -> None:
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=self.key(run_id, name),
                Body=data,
                ContentType=content_type,
                CacheControl="no-store",
            )
        except Exception as exc:
            raise StorageError("Could not store the record file") from exc

    def get(self, run_id: str, name: str) -> tuple[bytes, str]:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self.key(run_id, name))
            return response["Body"].read(), response.get("ContentType", "application/octet-stream")
        except Exception as exc:
            raise StorageError("Could not retrieve the record file") from exc

    def exists(self, run_id: str, name: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self.key(run_id, name))
            return True
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if str(code) in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise StorageError("Could not check the record file") from exc

    def delete_record(self, run_id: str) -> None:
        keys = [
            {"Key": self.key(run_id, name)}
            for name in ("original", "audio", "redacted", "overlay", "table")
        ]
        try:
            response = self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": keys})
            if response.get("Errors"):
                raise StorageError("Could not delete all record files")
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError("Could not delete record files") from exc


def configured_storage(settings: Any) -> PrivateObjectStorage | None:
    values = (
        settings.storage_bucket,
        settings.storage_endpoint,
        settings.storage_region,
        settings.storage_access_key,
        settings.storage_secret_key,
    )
    if not any(values):
        return None
    if not all(values):
        raise ValueError("Incomplete private object storage configuration")
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint,
        region_name=settings.storage_region,
        aws_access_key_id=settings.storage_access_key.get_secret_value(),
        aws_secret_access_key=settings.storage_secret_key.get_secret_value(),
        config=Config(
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 2},
        ),
    )
    return PrivateObjectStorage(client, settings.storage_bucket)
