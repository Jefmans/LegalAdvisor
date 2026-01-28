from fastapi import APIRouter
from elasticsearch import Elasticsearch

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


@router.get("/files/info/{filename}")
def get_file_info(filename: str):
    es = Elasticsearch("http://elasticsearch:9200")
    try:
        response = es.search(
            index="pdf_chunks",
            size=1,
            ignore_unavailable=True,
            body={
                "query": {"term": {"filename": filename}},
                "_source": ["language", "language_name", "section_patterns"],
            },
        )
    except Exception:
        return {"filename": filename, "language": None, "language_name": None, "section_patterns": []}

    hits = response.get("hits", {}).get("hits", [])
    if not hits:
        return {"filename": filename, "language": None, "language_name": None, "section_patterns": []}

    source = hits[0].get("_source", {}) or {}
    return {
        "filename": filename,
        "language": source.get("language"),
        "language_name": source.get("language_name"),
        "section_patterns": source.get("section_patterns") or [],
    }
