# app/db/models/question_orm.py
from sqlalchemy import Column, String, Enum
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
import enum
from uuid import uuid4

class QuestionStatus(str, enum.Enum):
    PROPOSED = "proposed"
    ASSIGNED = "assigned"
    CONSUMED = "consumed"

class QuestionORM(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    text = Column(String, unique=True, index=True, nullable=False)  # dedup by text
    source = Column(String, nullable=False)  # e.g. "root_subq" | "outline" | "expansion"
    status = Column(Enum(QuestionStatus), nullable=False, default=QuestionStatus.PROPOSED)
