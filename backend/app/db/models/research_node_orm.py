from uuid import uuid4

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class ResearchNodeORM(Base):
    __tablename__ = "research_nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(UUID(as_uuid=True), index=True, nullable=False)
    title = Column(String, nullable=False)
    goals = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    conclusion = Column(Text, nullable=True)
    rank = Column(Integer, nullable=False)
    level = Column(Integer, nullable=False)
    is_final = Column(Boolean, default=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("research_nodes.id"))

    # Self-referential relationship
    parent = relationship(
        "ResearchNodeORM",
        remote_side="ResearchNodeORM.id",
        back_populates="children",
    )

    children = relationship(
        "ResearchNodeORM",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
