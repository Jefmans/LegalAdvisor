import logging
from typing import Iterable, Optional, List
from elasticsearch import Elasticsearch, helpers

es = Elasticsearch("http://elasticsearch:9200")
logger = logging.getLogger(__name__)

PDF_CHUNKS = "pdf_chunks"
CAPTIONS = "captions"

PDF_CHUNKS_MAPPING = {
    "properties": {
        "id": {"type": "keyword"},
        "book_id": {"type": "keyword"},
        "source_pdf": {"type": "keyword"},
        "filename": {"type": "keyword"},
        "chunk_size": {"type": "integer"},
        "chunk_index": {"type": "integer"},
        "pages": {"type": "integer"},
        "text": {"type": "text"},
        "vector": {
            "type": "dense_vector",
            "dims": 1536,
            "index": True,
            "similarity": "cosine",
            "index_options": {"type": "int8_hnsw", "m": 16, "ef_construction": 100},
        },
    }
}

CAPTIONS_MAPPING = {
    "properties": {
        "id": {"type": "keyword"},
        "book_id": {"type": "keyword"},
        "source_pdf": {"type": "keyword"},
        "filename": {"type": "keyword"},
        "page_number": {"type": "integer"},
        "xref": {"type": "integer"},
        "text": {"type": "text"},
        "vector": {
            "type": "dense_vector",
            "dims": 1536,
            "index": True,
            "similarity": "cosine",
            "index_options": {"type": "int8_hnsw", "m": 16, "ef_construction": 100},
        },
    }
}

def _mapping_for(index: str) -> dict:
    return PDF_CHUNKS_MAPPING if index == PDF_CHUNKS else CAPTIONS_MAPPING

def ensure_index(name: str, mapping: dict):
    if not es.indices.exists(index=name):
        es.indices.create(index=name, mappings=mapping)

def ensure_all_indices():
    ensure_index(PDF_CHUNKS, PDF_CHUNKS_MAPPING)
    ensure_index(CAPTIONS, CAPTIONS_MAPPING)

def _vector_dims_from_mapping(mapping: dict) -> int:
    try:
        return int(mapping["properties"]["vector"]["dims"])
    except Exception:
        logger.warning("Couldn't read dims from mapping; defaulting to 1536")
        return 1536

def _coerce_pages(pages) -> List[int]:
    if pages is None:
        return []
    if isinstance(pages, list):
        return [int(p) for p in pages]
    try:
        return [int(pages)]
    except Exception:
        return []

def save_chunks_to_es(
    filename: str,
    chunks: Iterable,
    *,
    book_id: Optional[str] = None,
    source_pdf: Optional[str] = None,
    index: str = PDF_CHUNKS,
    batch_size: int = 500,
    request_timeout: int = 60,
    refresh: bool = False,
) -> dict:
    """
    Idempotently bulk-index chunks into `index` (default: pdf_chunks).

    - Stable doc_id: {filename}_{chunk_size}_{chunk_index}
    - Writes id/book_id/source_pdf/text/vector/etc. into _source
    - Validates vector length against the index mapping
    """
    mapping = _mapping_for(index)
    ensure_index(index, mapping)

    expected_dims = _vector_dims_from_mapping(mapping)
    total = 0
    successes = 0
    failures = 0

    def _actions():
        nonlocal total
        for ch in chunks:
            total += 1
            vec = getattr(ch, "embedding", None)
            if not isinstance(vec, list) or len(vec) != expected_dims:
                # Counted later from returned errors; we also log here for visibility
                logger.error(
                    "Skipping chunk: bad vector dims (got %s, expected %s). chunk_index=%s chunk_size=%s filename=%s",
                    None if vec is None else len(vec),
                    expected_dims,
                    getattr(ch, "chunk_index", "?"),
                    getattr(ch, "chunk_size", "?"),
                    filename,
                )
                continue

            doc_id = f"{filename}_{getattr(ch, 'chunk_size', 'NA')}_{getattr(ch, 'chunk_index', 'NA')}"
            yield {
                "_op_type": "index",      # overwrite-on-retry; use "create" to forbid overwrites
                "_index": index,
                "_id": doc_id,
                "_source": {
                    "id": doc_id,
                    "book_id": book_id,
                    "source_pdf": source_pdf or filename,
                    "filename": filename,
                    "chunk_size": int(getattr(ch, "chunk_size", 0)),
                    "chunk_index": int(getattr(ch, "chunk_index", 0)),
                    "pages": _coerce_pages(getattr(ch, "pages", [])),
                    "text": getattr(ch, "text", "") or "",
                    "vector": vec,
                },
            }

    try:
        success_count, errors = helpers.bulk(
            es,
            _actions(),
            chunk_size=batch_size,
            request_timeout=request_timeout,
            raise_on_error=False,
            stats_only=False,
        )
        successes = success_count
        failures = len(errors) if isinstance(errors, list) else 0

        if refresh:
            es.indices.refresh(index=index)

        return {"items": total, "success": successes, "fail": failures}
    except Exception as e:
        logger.exception("Bulk indexing failed for %s (%d chunks): %s", filename, total, e)
        return {"items": total, "success": successes, "fail": max(failures, 1), "error": str(e)}
