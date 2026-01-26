# app/mappers/outline_to_tree.py
from app.models.research_tree import ResearchNode

def node_from_outline_section(section) -> ResearchNode:
    node = ResearchNode(
        title=section.heading,
        goals=section.goals,
        questions=list(section.questions or []),
        subnodes=[node_from_outline_section(sub) for sub in section.subsections or []],
    )
    return node
