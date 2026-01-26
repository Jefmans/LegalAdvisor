import fitz
from typing import List
from app.utils.cleaning.header_footer import collect_repeating_lines, remove_repeating_lines
from app.utils.cleaning.page_numbers import detect_page_numbers, remove_page_numbers

def clean_document_text(pdf_path: str) -> List[str]:
    """Returns cleaned text per page (as joined string per page)."""
    with fitz.open(pdf_path) as doc:
        pages_text = [page.get_text().splitlines() for page in doc]

    # Step 1: Remove headers & footers
    header_set, footer_set = collect_repeating_lines(pages_text)
    pages_no_headers = remove_repeating_lines(pages_text, header_set, footer_set)

    # Step 2: Remove page numbers
    sequences = detect_page_numbers(pages_text)
    fully_cleaned = remove_page_numbers([page.splitlines() for page in pages_no_headers], sequences)

    return fully_cleaned  # list of strings (one per page)
 
