# app/utils/agent/repo.py
from typing import List, Iterable
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert  # <-- add this
from uuid import UUID

from app.db.models.research_node_orm import ResearchNodeORM
from app.db.models.chunk_orm import ChunkORM
from app.db.models.question_orm import QuestionORM, QuestionStatus
from app.db.models.node_chunk_orm import NodeChunkORM
from app.db.models.node_question_orm import NodeQuestionORM

def upsert_chunks(db: Session, chunks: Iterable[dict]) -> None:
    """
    chunks: iterable of dicts with keys: id (str), text, page?, source?
    De-dupes within this batch and inserts only missing ones.
    """
    # 1) De-dupe within-batch by id (first occurrence wins)
    by_id = {}
    for c in chunks:
        cid = c["id"]
        if cid not in by_id:
            by_id[cid] = c
    ids = list(by_id.keys())

    # 2) Filter out ones that already exist in DB
    existing_ids = {
        cid for (cid,) in db.query(ChunkORM.id).filter(ChunkORM.id.in_(ids)).all()
    }
    to_insert = [by_id[cid] for cid in ids if cid not in existing_ids]

    # 3) Bulk insert with ON CONFLICT DO NOTHING (protects again duplicates)
    if to_insert:
        stmt = pg_insert(ChunkORM.__table__).values(to_insert)
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
        db.execute(stmt)

    db.flush()

def attach_chunks_to_node(db: Session, node_id: UUID, chunk_ids: List[str]) -> None:
    if not chunk_ids:
        return
    chunk_ids = list(set(chunk_ids))  # de-dupe input list
    existing = {
        (nid, cid)
        for (nid, cid) in db.query(NodeChunkORM.node_id, NodeChunkORM.chunk_id)
            .filter(NodeChunkORM.node_id == node_id,
                    NodeChunkORM.chunk_id.in_(chunk_ids)).all()
    }
    for cid in chunk_ids:
        if (node_id, cid) not in existing:
            db.add(NodeChunkORM(node_id=node_id, chunk_id=cid))
    db.flush()


def get_node_chunks(db: Session, node_id: UUID) -> List[ChunkORM]:
    q = (db.query(ChunkORM)
           .join(NodeChunkORM, NodeChunkORM.chunk_id == ChunkORM.id)
           .filter(NodeChunkORM.node_id == node_id))
    return q.all()

# ---- Questions ----
def upsert_questions(db: Session, texts: List[str], source: str) -> List[UUID]:
    """
    Dedup by normalized text. Returns list of question IDs.
    """
    norm = [t.strip().lower() for t in texts]
    existing = db.query(QuestionORM).filter(func.lower(QuestionORM.text).in_(norm)).all()
    existing_map = {q.text.lower(): q for q in existing}

    ids = []
    for t in texts:
        key = t.strip().lower()
        if key in existing_map:
            q = existing_map[key]
            ids.append(q.id)
        else:
            q = QuestionORM(text=t.strip(), source=source, status=QuestionStatus.PROPOSED)
            db.add(q)
            db.flush()
            ids.append(q.id)
    return ids

def attach_questions_to_node(db: Session, node_id: UUID, question_ids: List[UUID]) -> None:
    if not question_ids:
        return
    existing = {
        (nid, qid) for (nid, qid) in db.query(NodeQuestionORM.node_id, NodeQuestionORM.question_id)
                                       .filter(NodeQuestionORM.node_id == node_id,
                                               NodeQuestionORM.question_id.in_(question_ids)).all()
    }
    for qid in question_ids:
        if (node_id, qid) not in existing:
            db.add(NodeQuestionORM(node_id=node_id, question_id=qid))
    # status bump to ASSIGNED
    db.query(QuestionORM).filter(QuestionORM.id.in_(question_ids),
                                 QuestionORM.status == QuestionStatus.PROPOSED)\
                         .update({QuestionORM.status: QuestionStatus.ASSIGNED}, synchronize_session=False)
    db.flush()

def get_node_questions(db: Session, node_id: UUID) -> List[QuestionORM]:
    q = (db.query(QuestionORM)
           .join(NodeQuestionORM, NodeQuestionORM.question_id == QuestionORM.id)
           .filter(NodeQuestionORM.node_id == node_id))
    return q.all()

def mark_questions_consumed(db: Session, question_ids: List[UUID]) -> None:
    if not question_ids:
        return
    db.query(QuestionORM)\
      .filter(QuestionORM.id.in_(question_ids))\
      .update({QuestionORM.status: QuestionStatus.CONSUMED}, synchronize_session=False)
    db.flush()





def update_node_fields(db, node_id, *, content=None, summary=None, conclusion=None, is_final=None):
    q = db.query(ResearchNodeORM).filter(ResearchNodeORM.id == node_id)
    updates = {}
    if content is not None: updates["content"] = content
    if summary is not None: updates["summary"] = summary
    if conclusion is not None: updates["conclusion"] = conclusion
    if is_final is not None: updates["is_final"] = is_final
    if updates:
        q.update(updates, synchronize_session=False)
        db.flush()
