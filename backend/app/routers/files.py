from elasticsearch import Elasticsearch
from fastapi import APIRouter

router = APIRouter()
es = Elasticsearch("http://elasticsearch:9200")


@router.get("/files/")
def list_files(limit: int = 200):
    try:
        response = es.search(
            index="pdf_chunks",
            size=0,
            ignore_unavailable=True,
            body={
                "aggs": {
                    "files": {
                        "terms": {"field": "filename", "size": limit, "order": {"_key": "asc"}}
                    }
                }
            },
        )
    except Exception:
        return {"files": []}

    buckets = response.get("aggregations", {}).get("files", {}).get("buckets", [])
    files = [bucket.get("key") for bucket in buckets if bucket.get("key")]
    return {"files": files}
