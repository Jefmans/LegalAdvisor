from typing import List, Optional

from elasticsearch import Elasticsearch, helpers
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.utils.summarize import summarize_texts
from app.utils.vectorstore import get_vectorstore

router = APIRouter()
vectorstore = get_vectorstore(index_name="pdf_chunks")


class SummaryRequest(BaseModel):
    filename: str
    max_chunks: Optional[int] = None
    model: str = "gpt-4o-mini"


class QuerySummaryRequest(BaseModel):
    query: str
    top_k: int = 5
    model: str = "gpt-4o-mini"


def _sort_key(item: tuple):
    page, chunk_index, _text = item
    page_key = page if page is not None else 1_000_000
    chunk_key = chunk_index if chunk_index is not None else 1_000_000
    return (page_key, chunk_key)


@router.post("/summarize/")
def summarize(req: SummaryRequest):
    es = Elasticsearch("http://elasticsearch:9200")

    query = {
        "query": {
            "term": {"filename": req.filename}
        }
    }

    chunks: List[tuple] = []
    for doc in helpers.scan(es, index="pdf_chunks", query=query, size=500):
        src = doc.get("_source", {})
        text = (src.get("text") or "").strip()
        if not text:
            continue
        pages = src.get("pages") or []
        page = pages[0] if isinstance(pages, list) and pages else None
        chunk_index = src.get("chunk_index")
        chunks.append((page, chunk_index, text))
        if req.max_chunks and len(chunks) >= req.max_chunks:
            break

    if not chunks:
        raise HTTPException(status_code=404, detail="No chunks found for this filename")

    chunks.sort(key=_sort_key)
    texts = [c[2] for c in chunks]
    summary = summarize_texts(texts, model=req.model)

    return {
        "filename": req.filename,
        "chunk_count": len(texts),
        "summary": summary,
    }


@router.post("/summarize_query/")
def summarize_query(req: QuerySummaryRequest):
    try:
        text_results = vectorstore.similarity_search_with_score(
            query=req.query, k=req.top_k
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")

    if not text_results:
        raise HTTPException(status_code=404, detail="No matches for this query")

    texts = [doc.page_content for (doc, _score) in text_results if doc.page_content]
    if not texts:
        raise HTTPException(status_code=404, detail="No text content for this query")

    summary = summarize_texts(texts, model=req.model)
    return {
        "query": req.query,
        "chunk_count": len(texts),
        "summary": summary,
    }
