from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, List
from dataclasses import dataclass


# --- Enum Definitions ---
class TypeCategory(str, Enum):
    book = "book"
    article = "article"
    thesis = "thesis"
    report = "report"
    unknown = "unknown"


class TopicCategory(str, Enum):
    fiction = "fiction"
    proza = "proza"
    poetry = "poetry"
    history = "history"
    physics = "physics"
    mathematics = "mathematics"
    computer_science = "computer science"
    politics = "politics"
    chemistry = "chemistry"
    biology = "biology"
    biography = "biography"
    law = "law"
    philosophy = "philosophy"
    religion = "religion"
    journalism = "journalism"
    medical = "medical"
    economy = "economy"
    finance = "finance"
    unknown = "unknown"


# --- Pydantic Schema ---
class DocumentMetadata(BaseModel):
    title: str = Field(..., description="the title of the book, might be black hole ")
    year: int = Field(..., description="The publication year (e.g. 2020)")
    type: TypeCategory = Field(..., description="The type of document")
    topic: TopicCategory = Field(..., description="The topic of document")
    authors: Optional[List[str]] = Field(None, description="All the authors")
    isbn: Optional[str] = Field(None, description="The ISBN number, if available")
    doi: Optional[str] = Field(None, description="The DOI, if available")
    publisher: Optional[str] = Field(None, description="The publisher of the book, if available")




class ImageMetadata(BaseModel):
    book_id: str
    source_pdf: str
    page_number: int
    xref: int
    filename: str
    caption: str = ""
    embedding: List = None



class TextChunkEmbedding(BaseModel):
    chunk_size: int
    chunk_index: int
    text: str
    pages: List[int]
    embedding: List[float]
