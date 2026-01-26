import hashlib
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app.db.db import SessionLocal
from app.mappers.outline_to_tree import node_from_outline_section
from app.models.research_tree import Chunk, ResearchNode, ResearchTree
from app.repositories.research_tree_repo import ResearchTreeRepository
from app.utils.agent.expander import create_subnodes_from_clusters, enrich_node_with_chunks_and_subquestions
from app.utils.agent.finalizer import finalize_article_from_tree
from app.utils.agent.outline import generate_outline_from_tree
from app.utils.agent.repo import (
    attach_chunks_to_node,
    attach_questions_to_node,
    get_node_chunks,
    get_node_questions,
    update_node_fields,
    upsert_chunks,
    upsert_questions,
)
from app.utils.agent.router_utils import (
    _filter_structural_sections,
    choose_best_node_for_question,
    get_top_level_section_or_400,
)
from app.utils.agent.search_chunks import search_chunks
from app.utils.agent.subquestions import generate_subquestions_from_chunks
from app.utils.agent.writer import write_conclusion, write_section, write_summary

router = APIRouter()


class AgentQueryRequest(BaseModel):
    query: str = "What is a black hole ?"
    top_k: int = 5


@router.post("/agent/query")
async def start_query_session(request: AgentQueryRequest):
    user_query = request.query
    top_chunks = search_chunks(user_query, top_k=request.top_k)

    root_node = ResearchNode(title=user_query)
    tree = ResearchTree(query=user_query, root_node=root_node)

    session_id = str(uuid4())
    db = SessionLocal()
    try:
        repo = ResearchTreeRepository(db)
        repo.save(tree, session_id)

        chunk_dicts = [
            {
                "id": hashlib.sha1(c.encode("utf-8")).hexdigest(),
                "text": c,
                "page": None,
                "source": None,
            }
            for c in top_chunks
        ]
        upsert_chunks(db, chunk_dicts)
        attach_chunks_to_node(db, tree.root_node.id, [c["id"] for c in chunk_dicts])
        db.commit()
    finally:
        db.close()

    return {
        "status": "success",
        "session_id": session_id,
        "query": user_query,
        "preview_chunks": top_chunks[:3],
    }


@router.post("/agent/subquestions")
def generate_subquestions(session_id: str):
    db = SessionLocal()
    try:
        repo = ResearchTreeRepository(db)
        tree = repo.load(session_id)

        if not tree:
            raise HTTPException(status_code=404, detail="ResearchTree not found")

        chunks = [c.text for n in tree.all_nodes() for c in n.chunks]
        chunks = list(dict.fromkeys(chunks))

        subq = generate_subquestions_from_chunks(chunks, tree.query)
        qids = upsert_questions(db, subq, source="root_subq")

        for qid, qtext in zip(qids, subq):
            best_node = choose_best_node_for_question(db, qtext, tree)
            attach_questions_to_node(db, best_node.id, [qid])

        db.commit()
    finally:
        db.close()
    return {"session_id": session_id, "questions": subq, "count": len(qids)}


@router.post("/agent/outline")
def create_outline(session_id: str):
    db = SessionLocal()
    try:
        repo = ResearchTreeRepository(db)
        tree = repo.load(session_id)
        outline = generate_outline_from_tree(tree)
        filtered_sections = _filter_structural_sections(outline.sections)
        tree.root_node.subnodes = [node_from_outline_section(s) for s in filtered_sections]

        if outline.title:
            tree.root_node.title = outline.title
        tree.assign_rank_and_level()

        repo.save(tree, session_id)

        def attach_all(section, node):
            if getattr(section, "questions", None):
                qids = upsert_questions(db, section.questions, source="outline")
                attach_questions_to_node(db, node.id, qids)
            for ssub, nsub in zip(section.subsections or [], node.subnodes or []):
                attach_all(ssub, nsub)

        for s, n in zip(filtered_sections, tree.root_node.subnodes):
            attach_all(s, n)

        db.commit()
        return {"session_id": session_id, "node_count": len(tree.root_node.subnodes)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Outline failed: {e}")
    finally:
        db.close()


@router.get("/agent/sections")
def list_sections(session_id: str):
    db = SessionLocal()
    try:
        repo = ResearchTreeRepository(db)
        tree = repo.load(session_id)
        nodes = [n for n in tree.all_nodes() if n.parent is not None]
        return {
            "session_id": session_id,
            "count": len(nodes),
            "sections": [
                {
                    "index": i,
                    "node_id": str(n.id),
                    "display_rank": n.display_rank,
                    "title": n.title,
                    "level": n.level,
                    "is_final": n.is_final,
                }
                for i, n in enumerate(nodes)
            ],
        }
    finally:
        db.close()


@router.post("/agent/section/{section_id}")
def write_section_by_id(session_id: str, section_id: int):
    db = SessionLocal()
    try:
        repo = ResearchTreeRepository(db)
        tree = repo.load(session_id)
        if not tree:
            raise HTTPException(status_code=404, detail="ResearchTree not found")

        node = get_top_level_section_or_400(tree, section_id)
        write_section(node)

        update_node_fields(db, node.id, content=node.content, is_final=True)
        db.commit()

        return {
            "session_id": session_id,
            "section_id": section_id,
            "heading": node.title,
            "text": node.content,
        }
    finally:
        db.close()


@router.post("/agent/expand/{section_id}")
def expand_section(session_id: str, section_id: int, top_k: int = 5):
    db = SessionLocal()
    try:
        repo = ResearchTreeRepository(db)
        tree = repo.load(session_id)
        if not tree:
            raise HTTPException(status_code=404, detail="ResearchTree not found")

        node = get_top_level_section_or_400(tree, section_id)
        before_ids = set(getattr(node, "chunk_ids", set()))

        enrich_node_with_chunks_and_subquestions(node, tree, top_k=top_k)

        # Refresh from DB so in-memory node reflects new attachments
        orm_chunks = get_node_chunks(db, node.id)
        node.chunks = [Chunk(id=c.id, text=c.text, page=c.page, source=c.source) for c in orm_chunks]
        node.chunk_ids = {c.id for c in orm_chunks}

        q_objs = get_node_questions(db, node.id)
        node.questions = [q.text for q in q_objs]

        new_chunks = [c for c in node.chunks if c.id not in before_ids]

        return {
            "status": "expanded",
            "section": node.title,
            "new_chunks": [c.text[:100] for c in new_chunks],
            "total_chunks": len(node.chunks),
            "questions": node.questions,
        }
    finally:
        db.close()


@router.get("/agent/deepen/debug/{section_id}")
def deepen_debug(session_id: str, section_id: int):
    from app.utils.agent.controller import get_novel_expansion_questions
    from app.utils.agent.repo import get_node_questions

    db = SessionLocal()
    try:
        repo = ResearchTreeRepository(db)
        tree = repo.load(session_id)
        node = get_top_level_section_or_400(tree, section_id)

        q_objs = get_node_questions(db, node.id)
        all_q = [{"text": q.text, "source": q.source, "status": q.status.value} for q in q_objs]

        novel = get_novel_expansion_questions(node, db, q_sim_thresh=0.80, title_sim_thresh=0.70)
        return {
            "section": node.title,
            "all_questions": all_q,
            "novel_expansion_candidates": novel,
            "child_titles": [c.title for c in node.subnodes],
        }
    finally:
        db.close()


@router.post("/agent/deepen/{section_id}")
def deepen_section(session_id: str, section_id: int, top_k: int = 5):
    from app.utils.agent.controller import get_novel_expansion_questions
    from app.utils.agent.title_from_cluster import title_from_cluster
    from app.utils.agent.topics import group_semantic

    db = SessionLocal()
    try:
        repo = ResearchTreeRepository(db)
        tree = repo.load(session_id)
        if not tree:
            raise HTTPException(status_code=404, detail="ResearchTree not found")

        node = get_top_level_section_or_400(tree, section_id)

        novel_expansion = get_novel_expansion_questions(
            node, db, q_sim_thresh=0.80, title_sim_thresh=0.70
        )
        if len(novel_expansion) < 2:
            return {"status": "skipped", "reason": "Not enough novel expansion questions"}

        clusters = group_semantic(novel_expansion, tau=None)
        big_enough = [c for c in clusters if len(c) >= 2]
        if not big_enough:
            big_enough = [[q] for q in novel_expansion]

        create_subnodes_from_clusters(node, big_enough, title_from_cluster, db=db)

        return {
            "status": "deepened",
            "clusters": [{"size": len(c), "sample": c[:2]} for c in clusters],
            "created_subnodes": [title_from_cluster(c) for c in big_enough],
        }
    finally:
        db.close()


@router.post("/agent/section/complete/{section_id}")
def complete_section(session_id: str, section_id: int):
    db = SessionLocal()
    try:
        repo = ResearchTreeRepository(db)
        tree = repo.load(session_id)
        if not tree:
            raise HTTPException(status_code=404, detail="ResearchTree not found")

        node = get_top_level_section_or_400(tree, section_id)

        node.summary = write_summary(node)
        node.conclusion = write_conclusion(node)
        update_node_fields(db, node.id, summary=node.summary, conclusion=node.conclusion, is_final=True)
        db.commit()

        return {
            "status": "success",
            "section_id": section_id,
            "summary": node.summary,
            "conclusion": node.conclusion,
        }
    finally:
        db.close()


@router.post("/agent/full_run")
def full_run(request: AgentQueryRequest):
    try:
        session_id = str(uuid4())
        user_query = request.query
        top_chunks = search_chunks(user_query, top_k=request.top_k)

        root_node = ResearchNode(title=request.query)
        tree = ResearchTree(query=user_query, root_node=root_node)

        db = SessionLocal()
        try:
            repo = ResearchTreeRepository(db)
            repo.save(tree, session_id)

            chunk_dicts = [
                {
                    "id": hashlib.sha1(c.encode("utf-8")).hexdigest(),
                    "text": c,
                    "page": None,
                    "source": None,
                }
                for c in top_chunks
            ]
            upsert_chunks(db, chunk_dicts)
            attach_chunks_to_node(db, tree.root_node.id, [c["id"] for c in chunk_dicts])
            db.commit()
        finally:
            db.close()

        db = SessionLocal()
        try:
            repo = ResearchTreeRepository(db)
            tree_for_subq = repo.load(session_id)
            root_chunks_text = [c.text for c in tree_for_subq.root_node.chunks]
        finally:
            db.close()

        subq = generate_subquestions_from_chunks(root_chunks_text, user_query)

        db = SessionLocal()
        try:
            repo = ResearchTreeRepository(db)
            tree_for_outline = repo.load(session_id)
        finally:
            db.close()

        outline = generate_outline_from_tree(tree_for_outline)
        filtered_sections = _filter_structural_sections(outline.sections)

        if not filtered_sections:
            from app.models.outline_model import OutlineSection

            filtered_sections = [
                OutlineSection(heading="Main Discussion", goals=None, questions=[], subsections=[])
            ]

        db = SessionLocal()
        try:
            repo = ResearchTreeRepository(db)
            tree = repo.load(session_id)

            tree.root_node.subnodes = [node_from_outline_section(s) for s in filtered_sections]
            if outline.title:
                tree.root_node.title = outline.title
            tree.assign_rank_and_level()
            repo.save(tree, session_id)

            def _attach_all(section, node):
                if getattr(section, "questions", None):
                    qids = upsert_questions(db, section.questions, source="outline")
                    attach_questions_to_node(db, node.id, qids)
                for ssub, nsub in zip(section.subsections or [], node.subnodes or []):
                    _attach_all(ssub, nsub)

            for s, n in zip(filtered_sections, tree.root_node.subnodes):
                _attach_all(s, n)

            if subq:
                qids = upsert_questions(db, subq, source="root_subq")
                for qid, qtext in zip(qids, subq):
                    best = choose_best_node_for_question(db, qtext, tree)
                    attach_questions_to_node(db, best.id, [qid])

            db.commit()
        finally:
            db.close()

        from app.utils.agent.expander import process_node_recursively

        section_outputs = []
        db = SessionLocal()
        try:
            repo = ResearchTreeRepository(db)
            tree = repo.load(session_id)

            for node in tree.root_node.subnodes:
                process_node_recursively(node, tree, top_k=10)

            tree = repo.load(session_id)

            def collect(n):
                out = [{"heading": n.title, "text": n.content or ""}]
                for c in n.subnodes:
                    out.extend(collect(c))
                return out

            for n in tree.root_node.subnodes:
                section_outputs.extend(collect(n))

            db.commit()
        finally:
            db.close()

        from app.utils.agent.writer import write_executive_summary, write_overall_conclusion

        db = SessionLocal()
        try:
            repo = ResearchTreeRepository(db)
            tree = repo.load(session_id)

            exec_summary = write_executive_summary(tree)
            overall_concl = write_overall_conclusion(tree)

            update_node_fields(
                db,
                tree.root_node.id,
                summary=exec_summary,
                conclusion=overall_concl,
                is_final=True,
            )
            db.commit()
        finally:
            db.close()

        db = SessionLocal()
        try:
            repo = ResearchTreeRepository(db)
            tree = repo.load(session_id)
            article = finalize_article_from_tree(tree)
        finally:
            db.close()

        return {
            "session_id": session_id,
            "title": tree.root_node.title or user_query,
            "abstract": tree.root_node.content or "",
            "outline": [s.dict() for s in filtered_sections],
            "sections": section_outputs,
            "article": article,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/tree/{session_id}")
def get_tree(session_id: str):
    db = SessionLocal()
    repo = ResearchTreeRepository(db)
    tree = repo.load(session_id)
    db.close()
    return JSONResponse(content=tree.model_dump_jsonable())


@router.get("/agent/export/pdf_latex")
def export_pdf_via_latex(session_id: str):
    import subprocess
    import tempfile
    from app.renderers.latex_deterministic import to_latex_deterministic

    db = SessionLocal()
    repo = ResearchTreeRepository(db)
    tree = repo.load(session_id)
    db.close()

    latex = to_latex_deterministic(tree)
    with tempfile.TemporaryDirectory() as tmp:
        tex = f"{tmp}/doc.tex"
        pdf = f"{tmp}/doc.pdf"
        with open(tex, "w") as f:
            f.write(latex)
        subprocess.run(["pdflatex", "-interaction=nonstopmode", tex], cwd=tmp, check=False)
        with open(pdf, "rb") as f:
            pdf_bytes = f.read()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=article.pdf"},
    )


@router.get("/agent/export/tree_content")
def export_tree_content(session_id: str):
    try:
        db = SessionLocal()
        repo = ResearchTreeRepository(db)
        tree = repo.load(session_id)
        db.close()
    except ValueError:
        raise HTTPException(status_code=404, detail="Tree not found in DB")

    def serialize_node(node):
        return {
            "title": node.title,
            "goals": node.goals,
            "questions": list(node.questions or []),
            "content": node.content,
            "summary": node.summary,
            "conclusion": node.conclusion,
            "rank": node.rank,
            "level": node.level,
            "parent_rank": node.parent.rank if node.parent else None,
            "parent_level": node.parent.level if node.parent else None,
            "display_rank": node.display_rank,
            "parent_title": node.parent_title,
            "node_id": str(node.id),
            "subnodes": [serialize_node(sub) for sub in node.subnodes],
        }

    return {"query": tree.query, "root_node": serialize_node(tree.root_node)}


@router.get("/agent/export/pdf_latex_tree")
def export_pdf_via_latex_tree(session_id: str):
    import subprocess
    import tempfile
    from app.renderers.latex_from_tree import to_latex_via_llm

    db = SessionLocal()
    repo = ResearchTreeRepository(db)
    tree = repo.load(session_id)
    db.close()

    latex = to_latex_via_llm(tree)

    with tempfile.TemporaryDirectory() as tmp:
        tex = f"{tmp}/doc.tex"
        pdf = f"{tmp}/doc.pdf"
        with open(tex, "w") as f:
            f.write(latex)
        subprocess.run(["pdflatex", "-interaction=nonstopmode", tex], cwd=tmp, check=False)
        with open(pdf, "rb") as f:
            pdf_bytes = f.read()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=article_tree_llm.pdf"},
    )


@router.get("/agent/export/pdf_latex_deterministic")
def export_pdf_via_latex_deterministic(session_id: str):
    import subprocess
    import tempfile
    from app.renderers.latex_deterministic import to_latex_deterministic

    db = SessionLocal()
    repo = ResearchTreeRepository(db)
    tree = repo.load(session_id)
    db.close()

    latex = to_latex_deterministic(tree)

    with tempfile.TemporaryDirectory() as tmp:
        tex = f"{tmp}/doc.tex"
        pdf = f"{tmp}/doc.pdf"
        with open(tex, "w") as f:
            f.write(latex)
        subprocess.run(["pdflatex", "-interaction=nonstopmode", tex], cwd=tmp, check=False)
        with open(pdf, "rb") as f:
            pdf_bytes = f.read()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=article_deterministic.pdf"},
    )
