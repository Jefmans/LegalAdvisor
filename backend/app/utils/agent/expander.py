import hashlib

from sqlalchemy import select

from app.db.db import SessionLocal
from app.db.models.question_orm import QuestionORM
from app.db.models.research_node_orm import ResearchNodeORM
from app.models.research_tree import ResearchNode, ResearchTree
from app.utils.agent.controller import get_novel_expansion_questions, should_deepen_node
from app.utils.agent.repo import (
    attach_chunks_to_node,
    attach_questions_to_node,
    update_node_fields,
    upsert_chunks,
    upsert_questions,
)
from app.utils.agent.search_chunks import search_chunks
from app.utils.agent.subquestions import generate_subquestions_from_chunks
from app.utils.agent.writer import write_section


def stable_chunk_id(text: str, meta_id: str | None = None) -> str:
    return meta_id or hashlib.sha1(text.encode("utf-8")).hexdigest()


def enrich_node_with_chunks_and_subquestions(
    node: ResearchNode,
    _tree: ResearchTree,
    top_k: int = 10,
) -> None:
    queries = [node.title] + getattr(node, "questions", [])
    combined_query = " ".join(q for q in queries if q).strip() or node.title

    results = search_chunks(combined_query, top_k=top_k, return_docs=True)

    chunk_dicts = []
    for doc in results:
        chunk_id = stable_chunk_id(
            doc.page_content,
            doc.metadata.get("id") or doc.metadata.get("_id"),
        )
        chunk_dicts.append(
            {
                "id": chunk_id,
                "text": doc.page_content,
                "page": doc.metadata.get("page"),
                "source": doc.metadata.get("source"),
            }
        )

    # De-dupe within this list before touching DB
    chunk_dicts = list({c["id"]: c for c in chunk_dicts}.values())

    db = SessionLocal()
    try:
        upsert_chunks(db, chunk_dicts)
        attach_chunks_to_node(db, node.id, [c["id"] for c in chunk_dicts])

        subqs = generate_subquestions_from_chunks([c["text"] for c in chunk_dicts], node.title)
        qids = upsert_questions(db, subqs, source="expansion")
        attach_questions_to_node(db, node.id, qids)

        db.commit()
    finally:
        db.close()


def deepen_node_with_subquestions(node: ResearchNode, questions: list[str], top_k: int = 5) -> None:
    db = SessionLocal()
    try:
        for q in questions:
            results = search_chunks(q, top_k=top_k, return_docs=True)
            chunk_dicts = []
            for doc in results:
                chunk_id = stable_chunk_id(doc.page_content, doc.metadata.get("id"))
                chunk_dicts.append(
                    {
                        "id": chunk_id,
                        "text": doc.page_content,
                        "page": doc.metadata.get("page"),
                        "source": doc.metadata.get("source"),
                    }
                )
            upsert_chunks(db, chunk_dicts)
            attach_chunks_to_node(db, node.id, [c["id"] for c in chunk_dicts])
        db.commit()
    finally:
        db.close()


def process_node_recursively(node: ResearchNode, tree: ResearchTree, top_k: int = 10) -> None:
    enrich_node_with_chunks_and_subquestions(node, tree, top_k=top_k)

    if should_deepen_node(node):
        db = SessionLocal()
        try:
            novel_expansion = get_novel_expansion_questions(
                node, db, q_sim_thresh=0.80, title_sim_thresh=0.70
            )
        finally:
            db.close()

        if novel_expansion:
            deepen_node_with_subquestions(node, novel_expansion, top_k=top_k)

    write_section(node)

    db = SessionLocal()
    try:
        update_node_fields(
            db,
            node.id,
            content=node.content,
            is_final=True,
        )
        db.commit()
    finally:
        db.close()

    for subnode in node.subnodes:
        process_node_recursively(subnode, tree, top_k=top_k)


def create_subnodes_from_clusters(
    node: ResearchNode,
    clusters_q: list[list[str]],
    cluster_title_fn,
    db=None,
) -> None:
    """
    For each cluster of question texts, create a child node under `node` and
    attach those questions to the new child. Titles come from cluster_title_fn.
    """
    local_db = db or SessionLocal()
    try:
        parent_orm = local_db.execute(
            select(ResearchNodeORM).where(ResearchNodeORM.id == node.id)
        ).scalar_one_or_none()
        if not parent_orm:
            return
        session_id = parent_orm.session_id

        q_rows = local_db.execute(select(QuestionORM.id, QuestionORM.text)).all()
        q_to_id = {text.lower(): qid for (qid, text) in q_rows}

        current_children_count = len(node.subnodes)

        for i, cluster in enumerate(clusters_q, start=1):
            if not cluster:
                continue
            title = cluster_title_fn(cluster)

            child_orm = ResearchNodeORM(
                session_id=session_id,
                parent_id=node.id,
                title=title,
                goals=None,
                content=None,
                summary=None,
                conclusion=None,
                rank=(current_children_count + i),
                level=(node.level or 1) + 1,
                is_final=False,
            )
            local_db.add(child_orm)
            local_db.flush()

            qids = [q_to_id.get(q.strip().lower()) for q in cluster]
            qids = [qid for qid in qids if qid]
            attach_questions_to_node(local_db, child_orm.id, qids)

        local_db.commit()
    finally:
        if db is None:
            local_db.close()
