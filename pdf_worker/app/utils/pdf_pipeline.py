import logging
from typing import List

import fitz  # PyMuPDF

from app.models import ImageMetadata
from app.utils.cleaning.clean_text_pipeline import clean_document_text
from app.utils.embed_captions import embed_and_store_captions
from app.utils.embedding import embed_chunks_streaming
from app.utils.es import save_chunks_to_es
from app.utils.image_extraction import process_images_and_captions
from app.utils.language import detect_language_from_pages
from app.utils.text_chunker import chunk_text
from app.utils.structure import detect_section_patterns_from_pages

logger = logging.getLogger(__name__)


def process_pdf(file_path: str, book_id: str, source_pdf: str) -> dict:
    logger.info("Starting full processing for: %s", source_pdf)

    cleaned_pages = clean_document_text(file_path)
    language_info = detect_language_from_pages(cleaned_pages)
    language_code = language_info.get("code")
    language_name = language_info.get("name")

    with fitz.open(file_path) as doc:
        page_range = list(range(len(doc)))

    image_records: List[ImageMetadata] = process_images_and_captions(
        pdf_path=file_path,
        page_range=page_range,
        book_id=book_id,
    )

    for img in image_records:
        if img.caption and img.caption.strip():
            page_idx = img.page_number - 1
            if 0 <= page_idx < len(cleaned_pages):
                cleaned_pages[page_idx] = "\n".join(
                    line
                    for line in cleaned_pages[page_idx].splitlines()
                    if img.caption.strip() not in line.strip()
                )

    section_patterns = detect_section_patterns_from_pages(
        cleaned_pages,
        language_code=language_code,
    )
    chunks = chunk_text(
        cleaned_pages,
        chunk_sizes=[400, 1600],
        language_code=language_code,
        section_patterns=section_patterns,
    )
    logger.info("Total chunks created: %s", len(chunks))

    embed_chunks_streaming(
        chunks,
        save_fn=lambda batch: save_chunks_to_es(
            source_pdf,
            batch,
            book_id=book_id,
            source_pdf=source_pdf,
            language=language_code,
        ),
    )

    embed_and_store_captions(image_records, language=language_code)

    chunks_count = len(chunks)
    captions_indexed = len([r for r in image_records if r.caption and r.caption.strip()])
    logger.info("Finished processing: %s", source_pdf)

    return {
        "pages": len(cleaned_pages),
        "chunks_indexed": chunks_count,
        "captions_indexed": captions_indexed,
        "language": language_code,
        "language_name": language_name,
    }
