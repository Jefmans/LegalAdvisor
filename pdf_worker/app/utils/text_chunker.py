from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List, Dict


def normalize_page_text(page: str) -> str:
    """
    Converts line-based page text to normalized paragraph text.
    """
    return ' '.join(line.strip() for line in page.splitlines() if line.strip())


def get_page_offsets(pages: List[str]) -> List[Dict]:
    """
    Returns a list of page start/end offsets for mapping chunks to pages.
    """
    page_offsets = []
    offset = 0
    for i, page in enumerate(pages, start=1):
        length = len(page)
        page_offsets.append({
            "page": i,
            "start": offset,
            "end": offset + length
        })
        offset += length + 2  # Account for \n\n joining
    return page_offsets


def map_chunk_to_pages(start: int, end: int, page_offsets: List[Dict]) -> List[int]:
    """
    Returns a list of pages overlapped by the chunk.
    """
    return [p["page"] for p in page_offsets if p["end"] >= start and p["start"] <= end]


def chunk_text(cleaned_pages: List[str], chunk_sizes: List[int]) -> List[Dict]:
    """
    Splits cleaned PDF text into multi-size overlapping chunks with page tracking.
    """
    # Step 1: Normalize
    normalized_pages = [normalize_page_text(page) for page in cleaned_pages]
    full_text = "\n\n".join(normalized_pages)
    page_offsets = get_page_offsets(normalized_pages)

    all_chunks = []

    for size in chunk_sizes:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=size,
            chunk_overlap=int(size * 0.2),
            separators=["\n\n", ".", "!", "?", "\n", " ", ""]
        )
        docs = splitter.create_documents([full_text])

        cursor = 0  # tracks last match
        for i, doc in enumerate(docs):
            chunk_text = doc.page_content
            start = full_text.find(chunk_text, cursor)
            if start == -1:
                # fallback to brute match
                start = full_text.index(chunk_text)
            end = start + len(chunk_text)
            cursor = end

            pages = map_chunk_to_pages(start, end, page_offsets)

            all_chunks.append({
                "chunk_size": size,
                "chunk_index": i,
                "text": chunk_text,
                "pages": pages
            })

    return all_chunks
