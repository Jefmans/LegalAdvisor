# app/db/models/node_question_orm.py
from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class NodeQuestionORM(Base):
    __tablename__ = "node_questions"
    node_id = Column(UUID(as_uuid=True), ForeignKey("research_nodes.id", ondelete="CASCADE"), primary_key=True)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True)

    __table_args__ = (
        UniqueConstraint("node_id", "question_id", name="uq_node_question"),
    )
