from difflib import SequenceMatcher
from fastapi import HTTPException
from app.models.research_tree import ResearchTree, ResearchNode

def choose_best_node_for_question(_db, qtext: str, tree: ResearchTree) -> ResearchNode:
    # naive: pick the top-level node with the most similar title
    def best(node_list):
        scores = [(SequenceMatcher(None, qtext.lower(), n.title.lower()).ratio(), n) for n in node_list]
        return max(scores, key=lambda x: x[0])[1] if scores else tree.root_node
    # prefer children if present
    if tree.root_node.subnodes:
        return best(tree.root_node.subnodes)
    return tree.root_node


def get_top_level_section_or_400(tree: ResearchTree, section_id: int) -> ResearchNode:
    subs = tree.root_node.subnodes or []
    if not subs:
        raise HTTPException(status_code=400, detail="No sections available; outline is empty.")
    if section_id < 0 or section_id >= len(subs):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid section_id: {section_id}. Valid range: 0..{len(subs)-1}"
        )
    return subs[section_id]


def _filter_structural_sections(sections):
    blocklist = {"conclusion", "overall conclusion", "executive summary", "summary", "abstract"}
    def keep(s):
        return s.heading.strip().lower() not in blocklist
    return [s for s in sections if keep(s)]