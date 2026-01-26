# app/utils/agent/controller.py
from difflib import SequenceMatcher
from typing import List
from app.utils.agent.repo import get_node_questions
from app.db.models.question_orm import QuestionStatus
from app.db.models.research_node_orm import ResearchNodeORM
from app.db.models.node_question_orm import NodeQuestionORM
from app.db.models.question_orm import QuestionORM

# --- helpers --------------------------------------------------------------

def _similar(a: str, b: str, thresh: float) -> bool:
    return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio() >= thresh

def _is_novel(candidate: str, against: List[str], thresh: float) -> bool:
    return all(not _similar(candidate, ex, thresh) for ex in against)

# If you want the actual list of novel expansion questions (optional)
def get_novel_expansion_questions(node, db, q_sim_thresh: float, title_sim_thresh: float) -> List[str]:
    """
    Returns the subset of this node's ASSIGNED expansion questions that are:
    - novel vs. this node's non-expansion questions
    - novel vs. all other nodes' questions in the same session
    - not overlapping with existing child titles
    """
    # 1) All questions on this node
    q_objs = get_node_questions(db, node.id)

    # expansion candidates we'll test for novelty
    expansion_q = [
        q.text for q in q_objs
        if q.status == QuestionStatus.ASSIGNED and (q.source or "").lower() == "expansion"
    ]
    if not expansion_q:
        return []

    # local baseline (non-expansion)
    local_existing = [
        q.text for q in q_objs
        if (q.source or "").lower() != "expansion"
    ]

    # 2) Resolve session_id for this node
    rn = db.query(ResearchNodeORM).filter(ResearchNodeORM.id == node.id).first()
    if not rn:
        return []  # defensive

    # 3) Global baseline: all other nodes' questions in the same session
    other_q_texts = (
        db.query(QuestionORM.text)
          .join(NodeQuestionORM, NodeQuestionORM.question_id == QuestionORM.id)
          .join(ResearchNodeORM, ResearchNodeORM.id == NodeQuestionORM.node_id)
          .filter(ResearchNodeORM.session_id == rn.session_id,
                  ResearchNodeORM.id != node.id)
          .all()
    )
    global_existing = [t for (t,) in other_q_texts]

    # 4) Child titles to avoid duplicating subnodes
    child_titles = [c.title for c in getattr(node, "subnodes", []) or []]

    # 5) Novelty filter
    novel = []
    for cand in expansion_q:
        if not _is_novel(cand, local_existing, q_sim_thresh):
            continue
        if not _is_novel(cand, global_existing, q_sim_thresh):
            continue
        if not _is_novel(cand, child_titles, title_sim_thresh):
            continue
        novel.append(cand)

    return novel

# --- main decision --------------------------------------------------------

def should_deepen_node(
    node,
    similarity_threshold: float = 0.80,   # question-to-question novelty
    min_novel: int = 2,
    title_similarity_threshold: float = 0.70  # question vs child-title
) -> bool:
    """
    Decide to deepen if there are >= min_novel ASSIGNED expansion questions
    that are novel vs. (a) this node's non-expansion questions,
    (b) all other nodes' questions in the same session, and
    (c) existing child titles (to avoid duplicate subnodes).
    """
    from app.db.db import SessionLocal
    db = SessionLocal()
    try:
        novel_expansion = get_novel_expansion_questions(
            node,
            db,
            q_sim_thresh=similarity_threshold,
            title_sim_thresh=title_similarity_threshold,
        )
        return len(novel_expansion) >= min_novel
    finally:
        db.close()
