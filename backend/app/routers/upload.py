from fastapi import APIRouter, UploadFile, File, HTTPException
from app.utils.minio_client import get_minio_client
from pydantic import BaseModel
import uuid
import io
import requests
from urllib.parse import urlparse

router = APIRouter()

minio_client = get_minio_client()

BUCKET_NAME = "uploads"

@router.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Generate a unique file name
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        content = await file.read()

        # Wrap bytes in a stream
        stream = io.BytesIO(content)        

        minio_client.put_object(
            bucket_name=BUCKET_NAME,
            object_name=unique_filename,
            data=stream,
            length=len(content),
            content_type=file.content_type,
        )

        return {
            "filename": unique_filename,
            "link": f"/minio/uploads/{unique_filename}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class UploadUrlRequest(BaseModel):
    url: str
    filename: str | None = None


@router.post("/upload_url/")
def upload_url(payload: UploadUrlRequest):
    try:
        parsed = urlparse(payload.url)
        if parsed.scheme not in {"http", "https"}:
            raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

        response = requests.get(payload.url, timeout=30)
        response.raise_for_status()
        content = response.content

        basename = payload.filename
        if not basename:
            basename = parsed.path.split("/")[-1] or "source.html"
        if not basename.lower().endswith((".html", ".htm")):
            basename = f"{basename}.html"

        unique_filename = f"{uuid.uuid4()}_{basename}"
        stream = io.BytesIO(content)

        minio_client.put_object(
            bucket_name=BUCKET_NAME,
            object_name=unique_filename,
            data=stream,
            length=len(content),
            content_type="text/html",
        )

        return {
            "filename": unique_filename,
            "source_url": payload.url,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
