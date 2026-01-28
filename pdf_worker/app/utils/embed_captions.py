import logging
import os
from typing import List

from elasticsearch import helpers
from langchain_openai import OpenAIEmbeddings

from app.models import ImageMetadata
from app.utils.es import CAPTIONS, CAPTIONS_MAPPING, ensure_index, es

logger = logging.getLogger(__name__)

# Initialize embedding model
embedding_model = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )


def embed_and_store_captions(
    records: List[ImageMetadata],
    index_name: str = CAPTIONS,
    *,
    language: str | None = None,
    language_name: str | None = None,
    section_patterns: List[str] | None = None,
):
    """
    Embed caption texts from ImageMetadata list and index them in Elasticsearch.
    """
    ensure_index(index_name, CAPTIONS_MAPPING)
    # Filter records that have a caption
    valid_records = [r for r in records if r.caption and r.caption.strip()]
    if not valid_records:
        logger.info("No valid captions to embed.")
        return

    texts = [r.caption for r in valid_records]
    embeddings = embedding_model.embed_documents(texts)

    payloads = []
    for record, embedding in zip(valid_records, embeddings):
        doc_id = f"{record.book_id}_{record.page_number}_{record.xref}"
        payloads.append({
            "_index": index_name,
            "_id": doc_id,
            "_source": {
                "book_id": record.book_id,
                "page_number": record.page_number,
                "text": record.caption,
                # "embedding": embedding,
                "vector": embedding,
                "source_pdf": record.source_pdf,
                "xref": record.xref,
                "filename": record.filename,
                "language": language,
                "language_name": language_name,
                "section_patterns": section_patterns,
                "metadata": {
                    "book_id": record.book_id,
                    "page_number": record.page_number,
                    "source_pdf": record.source_pdf,
                    "xref": record.xref,
                    "filename": record.filename,
                    "language": language,
                    "language_name": language_name,
                    "section_patterns": section_patterns,
                },
            }
        })

    helpers.bulk(es, payloads)
    logger.info("Embedded and indexed %s captions into '%s'", len(payloads), index_name)
