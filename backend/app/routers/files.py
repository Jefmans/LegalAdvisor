from fastapi import APIRouter

from app.utils.minio_client import get_minio_client

router = APIRouter()


@router.get("/files/")
def list_files(limit: int = 200):
    client = get_minio_client()
    files = []
    try:
        for obj in client.list_objects("uploads", recursive=True):
            if getattr(obj, "is_dir", False):
                continue
            if obj.object_name:
                files.append(obj.object_name)
            if len(files) >= limit:
                break
    except Exception:
        return {"files": []}

    return {"files": sorted(files)}
