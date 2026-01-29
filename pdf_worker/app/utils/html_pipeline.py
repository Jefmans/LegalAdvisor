import logging
import re
from typing import List

from bs4 import BeautifulSoup

from app.utils.embedding import embed_chunks_streaming
from app.utils.es import save_chunks_to_es
from app.utils.language import detect_language_from_pages
from app.utils.structure import detect_section_patterns_from_pages
from app.utils.text_chunker import chunk_text

logger = logging.getLogger(__name__)


def _detect_html_encoding(raw: bytes) -> str:
    match = re.search(br"charset=['\"]?([A-Za-z0-9._-]+)", raw[:5000], re.IGNORECASE)
    if match:
        try:
            return match.group(1).decode("ascii", "ignore") or "utf-8"
        except Exception:
            return "utf-8"
    return "utf-8"


def _extract_main_text(html_text: str) -> str:
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "header", "nav", "footer"]):
        tag.decompose()

    main = soup.select_one("div.list") or soup.select_one("main") or soup.body or soup
    for br in main.find_all("br"):
        br.replace_with("\n")

    text = main.get_text("\n")
    text = text.replace("\xa0", " ")
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def process_html(file_path: str, book_id: str, source_name: str) -> dict:
    logger.info("Starting HTML processing for: %s", source_name)

    raw = None
    with open(file_path, "rb") as handle:
        raw = handle.read()

    encoding = _detect_html_encoding(raw)
    html_text = raw.decode(encoding, errors="ignore")

    extracted = _extract_main_text(html_text)
    pages = [extracted] if extracted else []

    language_info = detect_language_from_pages(pages)
    language_code = language_info.get("code")
    language_name = language_info.get("name")

    section_patterns = detect_section_patterns_from_pages(
        pages,
        language_code=language_code,
    )

    chunks = chunk_text(
        pages,
        chunk_sizes=[800, 1600],
        language_code=language_code,
        section_patterns=section_patterns,
    )

    embed_chunks_streaming(
        chunks,
        save_fn=lambda batch: save_chunks_to_es(
            source_name,
            batch,
            book_id=book_id,
            source_pdf=source_name,
            language=language_code,
            language_name=language_name,
            section_patterns=section_patterns,
        ),
    )

    logger.info("Finished HTML processing: %s", source_name)
    return {
        "pages": len(pages),
        "chunks_indexed": len(chunks),
        "captions_indexed": 0,
        "language": language_code,
        "language_name": language_name,
        "section_patterns": section_patterns,
        "source_type": "html",
    }
