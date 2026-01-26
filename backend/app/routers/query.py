from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.utils.vectorstore import get_vectorstore

router = APIRouter()
vectorstore = get_vectorstore(index_name="pdf_chunks")
caption_store = get_vectorstore(index_name="captions")


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/query/")
async def query(request: QueryRequest):
    try:
        text_results = vectorstore.similarity_search_with_score(
            query=request.query, k=request.top_k
        )
        caption_results = caption_store.similarity_search_with_score(
            query=request.query, k=request.top_k
        )

        return {
            "text_chunks": [
                {
                    "text": doc.page_content,
                    "score": score,
                    "metadata": dict(doc.metadata or {}),
                }
                for (doc, score) in text_results
            ],
            "captions": [
                {
                    "text": doc.page_content,
                    "score": score,
                    "metadata": dict(doc.metadata or {}),
                }
                for (doc, score) in caption_results
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")
