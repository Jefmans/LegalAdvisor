# app/db/models/chunk_orm.py
from sqlalchemy import Column, String, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class ChunkORM(Base):
    __tablename__ = "chunks"

    # Use ES doc id if you have it (string, stable)
    id = Column(String, primary_key=True)  # ES id or stable hash
    text = Column(Text, nullable=False)
    page = Column(Integer, nullable=True)
    source = Column(String, nullable=True)
    # Optional: embedding stored elsewhere (ES). If in PG, add a vector column.
