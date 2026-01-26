# app/db/models/node_chunk_orm.py
from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class NodeChunkORM(Base):
    __tablename__ = "node_chunks"
    node_id = Column(UUID(as_uuid=True), ForeignKey("research_nodes.id", ondelete="CASCADE"), primary_key=True)
    chunk_id = Column(ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True)

    __table_args__ = (
        UniqueConstraint("node_id", "chunk_id", name="uq_node_chunk"),
    )
