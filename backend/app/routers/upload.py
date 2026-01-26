from fastapi import APIRouter, UploadFile, File, HTTPException
from app.utils.minio_client import get_minio_client
import uuid
import io

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
