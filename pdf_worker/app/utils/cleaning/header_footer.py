from typing import List, Set, Tuple

from rapidfuzz import fuzz


def normalize(line: str) -> str:
    return line.strip().lower()


def collect_repeating_lines(
    pages_text: List[List[str]],
    n: int = 5,
    lookahead: int = 2,
    threshold: int = 100,
) -> Tuple[Set[str], Set[str]]:
    """
    Scan pages and collect repeated header/footer lines.
    `threshold` is an exact match at 100, or set lower (e.g. 85) for fuzzy matches.
    """
    header_candidates = set()
    footer_candidates = set()

    for i, page in enumerate(pages_text):
        top_lines = [normalize(line) for line in page[:n]]
        bottom_lines = [normalize(line) for line in page[-n:]]

        for j in range(1, lookahead + 1):
            if i + j >= len(pages_text):
                break

            next_top = [normalize(line) for line in pages_text[i + j][:n]]
            next_bottom = [normalize(line) for line in pages_text[i + j][-n:]]

            for line in top_lines:
                if line and any(fuzz.ratio(line, other) >= threshold for other in next_top):
                    header_candidates.add(line)

            for line in bottom_lines:
                if line and any(fuzz.ratio(line, other) >= threshold for other in next_bottom):
                    footer_candidates.add(line)

    return header_candidates, footer_candidates


def remove_repeating_lines(
    pages_text: List[List[str]],
    header_set: Set[str],
    footer_set: Set[str],
    n: int = 5,
) -> List[str]:
    """
    Remove known header/footer lines within the top/bottom `n` lines of each page.
    Returns list of cleaned page strings.
    """
    cleaned_pages = []

    for page in pages_text:
        cleaned = []
        for i, line in enumerate(page):
            norm = normalize(line)
            is_header_zone = i < n
            is_footer_zone = i >= len(page) - n

            if is_header_zone and norm in header_set:
                continue
            if is_footer_zone and norm in footer_set:
                continue

            cleaned.append(line)

        cleaned_pages.append("\n".join(cleaned))

    return cleaned_pages
