import io
import os
from minio import Minio


def get_minio_client() -> Minio:
    endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
    access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
    secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
    return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)


def download_from_minio(filename: str, bucket: str = "uploads") -> str:
    client = get_minio_client()
    local_path = f"/tmp/{filename}"
    client.fget_object(bucket, filename, local_path)
    return local_path


def upload_bytes_to_minio(
    bucket: str,
    object_name: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> None:
    client = get_minio_client()
    stream = io.BytesIO(data)
    stream.seek(0)
    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=stream,
        length=len(data),
        content_type=content_type,
    )
