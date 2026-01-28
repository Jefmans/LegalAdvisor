from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List, Dict, Optional
import re


SECTION_PATTERNS = {
    "en": [
        r"\bArticle\s+\d+[A-Za-z0-9\-\.]*",
        r"\bSection\s+\d+[A-Za-z0-9\-\.]*",
        r"\bChapter\s+[IVXLC0-9]+",
        r"\bTitle\s+[IVXLC0-9]+",
        r"§\s*\d+[A-Za-z0-9\-\.]*",
    ]
}


def normalize_page_text(page: str) -> str:
    """
    Converts line-based page text to normalized paragraph text.
    """
    return " ".join(line.strip() for line in page.splitlines() if line.strip())


def _select_section_patterns(language_code: Optional[str]) -> List[str]:
    if not language_code:
        return []
    return SECTION_PATTERNS.get(language_code, [])


def _count_section_matches(full_text: str, patterns: List[str]) -> int:
    if not full_text or not patterns:
        return 0
    count = 0
    for pattern in patterns:
        for _ in re.finditer(pattern, full_text, flags=re.IGNORECASE):
            count += 1
            if count >= 2:
                return count
    return count


def _split_into_sections(full_text: str, patterns: List[str]) -> List[Dict]:
    if not full_text:
        return []

    if not patterns:
        return [{"start": 0, "end": len(full_text), "text": full_text}]

    starts = set()
    for pattern in patterns:
        for match in re.finditer(pattern, full_text, flags=re.IGNORECASE):
            starts.add(match.start())

    if not starts:
        return [{"start": 0, "end": len(full_text), "text": full_text}]

    ordered = sorted(starts)
    if ordered[0] != 0:
        ordered.insert(0, 0)

    sections = []
    for idx, start in enumerate(ordered):
        end = ordered[idx + 1] if idx + 1 < len(ordered) else len(full_text)
        sections.append({"start": start, "end": end, "text": full_text[start:end]})
    return sections


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


def chunk_text(
    cleaned_pages: List[str],
    chunk_sizes: List[int],
    *,
    language_code: Optional[str] = None,
    section_patterns: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Splits cleaned PDF text into multi-size overlapping chunks with page tracking.
    """
    # Step 1: Normalize
    normalized_pages = [normalize_page_text(page) for page in cleaned_pages]
    full_text = "\n\n".join(normalized_pages)
    page_offsets = get_page_offsets(normalized_pages)
    patterns = section_patterns if section_patterns is not None else _select_section_patterns(language_code)
    if section_patterns:
        if _count_section_matches(full_text, section_patterns) < 2:
            patterns = _select_section_patterns(language_code)
    sections = _split_into_sections(full_text, patterns)

    all_chunks = []

    for size in chunk_sizes:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=size,
            chunk_overlap=int(size * 0.2),
            separators=["\n\n", ".", "!", "?", "\n", " ", ""]
        )
        chunk_index = 0

        for section in sections:
            section_text = section["text"]
            if not section_text or not section_text.strip():
                continue

            if len(section_text) <= size:
                start = section["start"]
                end = section["end"]
                pages = map_chunk_to_pages(start, end, page_offsets)
                all_chunks.append({
                    "chunk_size": size,
                    "chunk_index": chunk_index,
                    "text": section_text,
                    "pages": pages
                })
                chunk_index += 1
                continue

            docs = splitter.create_documents([section_text])
            cursor = 0  # tracks last match within section
            for doc in docs:
                content = doc.page_content
                start_in_section = section_text.find(content, cursor)
                if start_in_section == -1:
                    # fallback to brute match
                    start_in_section = section_text.index(content)
                end_in_section = start_in_section + len(content)
                cursor = end_in_section

                start = section["start"] + start_in_section
                end = section["start"] + end_in_section
                pages = map_chunk_to_pages(start, end, page_offsets)

                all_chunks.append({
                    "chunk_size": size,
                    "chunk_index": chunk_index,
                    "text": content,
                    "pages": pages
                })
                chunk_index += 1

    return all_chunks
