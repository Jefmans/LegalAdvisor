# app/repositories/research_tree_repo.py
from __future__ import annotations
from typing import Dict, List
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.research_tree import ResearchTree, ResearchNode, Chunk
from app.db.models.research_node_orm import ResearchNodeORM
from app.db.models.node_question_orm import NodeQuestionORM
from app.db.models.question_orm import QuestionORM
from app.db.models.node_chunk_orm import NodeChunkORM
from app.db.models.chunk_orm import ChunkORM
from app.db.db import Session as SessionModel


class ResearchTreeRepository:
    def __init__(self, db: Session):
        self.db = db

    # ---------- SAVE ----------
    def save(self, tree: ResearchTree, session_id: str) -> None:
        """Persist or update the whole tree structure under a session_id."""
        def _upsert(node: ResearchNode, parent_id: UUID | None):
            db_node = self.db.query(ResearchNodeORM).filter_by(id=node.id).first()
            if db_node is None:
                db_node = ResearchNodeORM(
                    id=node.id,
                    session_id=session_id,
                    parent_id=parent_id,
                    title=node.title,
                    goals=node.goals,
                    content=node.content,
                    summary=node.summary,
                    conclusion=node.conclusion,
                    rank=node.rank,
                    level=node.level,
                    is_final=node.is_final,
                )
                self.db.add(db_node)
            else:
                db_node.parent_id = parent_id
                db_node.title = node.title
                db_node.goals = node.goals
                db_node.content = node.content
                db_node.summary = node.summary
                db_node.conclusion = node.conclusion
                db_node.rank = node.rank
                db_node.level = node.level
                db_node.is_final = node.is_final

            self.db.flush()
            for child in node.subnodes:
                _upsert(child, db_node.id)

        # ensure session row exists (stores query + optional snapshot if you want)
        sess = self.db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if sess is None:
            self.db.add(SessionModel(id=session_id, query=tree.query, tree={}))

        _upsert(tree.root_node, parent_id=None)
        self.db.commit()

    # ---------- LOAD ----------
    def load(self, session_id: str) -> ResearchTree:
        sess = self.db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not sess:
            raise ValueError("Session not found")
        original_query = sess.query

        roots = (
            self.db.query(ResearchNodeORM)
            .filter(ResearchNodeORM.session_id == session_id,
                    ResearchNodeORM.parent_id == None)  # noqa: E711
            .all()
        )
        if not roots:
            raise ValueError("No root node found")
        root_orm = roots[0]

        all_orm = (
            self.db.query(ResearchNodeORM)
            .filter(ResearchNodeORM.session_id == session_id)
            .all()
        )

        # id -> in-memory node
        id_map: Dict[UUID, ResearchNode] = {}
        for orm in all_orm:
            node = ResearchNode.from_orm_model(orm)
            id_map[node.id] = node

        # link children
        for orm in all_orm:
            if orm.parent_id:
                parent = id_map[orm.parent_id]
                child = id_map[orm.id]
                child.parent = parent 
                parent.subnodes.append(child)

        # hydrate questions
        q_rows = (
            self.db.query(NodeQuestionORM.node_id, QuestionORM.text)
            .join(QuestionORM, QuestionORM.id == NodeQuestionORM.question_id)
            .filter(NodeQuestionORM.node_id.in_(list(id_map.keys())))
            .all()
        )
        q_by_node: Dict[UUID, List[str]] = {}
        for nid, qtext in q_rows:
            q_by_node.setdefault(nid, []).append(qtext)

        # hydrate chunks
        c_rows = (
            self.db.query(NodeChunkORM.node_id, ChunkORM.id, ChunkORM.text, ChunkORM.page, ChunkORM.source)
            .join(ChunkORM, ChunkORM.id == NodeChunkORM.chunk_id)
            .filter(NodeChunkORM.node_id.in_(list(id_map.keys())))
            .all()
        )
        c_by_node: Dict[UUID, List[Chunk]] = {}
        for nid, cid, ctext, cpage, csrc in c_rows:
            c_by_node.setdefault(nid, []).append(Chunk(id=cid, text=ctext, page=cpage, source=csrc))

        for nid, node in id_map.items():
            node.questions = q_by_node.get(nid, [])
            node.chunks = c_by_node.get(nid, [])
            node.chunk_ids = {c.id for c in node.chunks}

        return ResearchTree(query=original_query, root_node=id_map[root_orm.id])
