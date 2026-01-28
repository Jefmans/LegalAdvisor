from typing import List, Optional

from elasticsearch import Elasticsearch, helpers
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.utils.summarize import summarize_texts
from app.utils.vectorstore import get_vectorstore
from app.utils.language import detect_language

router = APIRouter()
vectorstore = get_vectorstore(index_name="pdf_chunks")


class SummaryRequest(BaseModel):
    filename: str
    max_chunks: Optional[int] = None
    model: str = "gpt-4o-mini"
    language: Optional[str] = None


class QuerySummaryRequest(BaseModel):
    query: str
    top_k: int = 5
    model: str = "gpt-4o-mini"


class TextsSummaryRequest(BaseModel):
    texts: List[str]
    model: str = "gpt-4o-mini"
    query: Optional[str] = None
    language: Optional[str] = None


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
    language_info = detect_language(req.query)
    summary = summarize_texts(texts, model=req.model, language_name=language_info.get("name"))

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

    language_name = req.language
    if not language_name:
        sample = texts[0] if texts else req.filename
        language_info = detect_language(sample)
        language_name = language_info.get("name")
    summary = summarize_texts(texts, model=req.model, language_name=language_name)
    return {
        "query": req.query,
        "chunk_count": len(texts),
        "summary": summary,
    }


@router.post("/summarize_texts/")
def summarize_texts_endpoint(req: TextsSummaryRequest):
    cleaned = [text.strip() for text in req.texts if text and text.strip()]
    if not cleaned:
        raise HTTPException(status_code=400, detail="No texts provided")

    language_name = req.language
    if not language_name:
        sample = req.query or cleaned[0]
        language_info = detect_language(sample)
        language_name = language_info.get("name")

    summary = summarize_texts(cleaned, model=req.model, language_name=language_name)
    return {
        "chunk_count": len(cleaned),
        "summary": summary,
    }
