# app/schemas.py
from pydantic import BaseModel
from typing import Optional, List

class ImageMetadata(BaseModel):
    book_id: str
    source_pdf: str
    page_number: int
    xref: int
    filename: str
    caption: Optional[str] = ""
    embedding: Optional[List[float]] = None  # Optional for later use

    class Config:
        from_attributes = True
