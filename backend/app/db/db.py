# app/db/db.py
from sqlalchemy import create_engine, Column, String, Integer, Table, TIMESTAMP, ARRAY
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid

from app.db.base import Base  # <-- use the single shared Base

DATABASE_URL = "postgresql://test:test@postgres:5432/testdb"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Session(Base):
    __tablename__ = "sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query = Column(String, nullable=False)
    tree = Column(JSONB, nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    title = Column(String)
    year = Column(Integer)
    type = Column(String)
    topic = Column(String)
    authors = Column(ARRAY(String))
    isbn = Column(String)
    doi = Column(String)
    publisher = Column(String)
    created_at = Column(TIMESTAMP)

class ImageRecord(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(String, index=True)
    source_pdf = Column(String)
    page_number = Column(Integer)
    xref = Column(Integer)
    filename = Column(String, unique=True)
    caption = Column(String)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
