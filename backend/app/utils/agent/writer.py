from textwrap import dedent

from langchain_openai import ChatOpenAI

from app.db.db import SessionLocal
from app.models.research_tree import ResearchNode, ResearchTree
from app.utils.agent.repo import get_node_chunks, get_node_questions, mark_questions_consumed
llm = ChatOpenAI(model="gpt-4o", temperature=0)


def write_section(node: ResearchNode) -> ResearchNode:
    db = SessionLocal()
    try:
        q_objs = get_node_questions(db, node.id)
        questions = [q.text for q in q_objs]
        chunks = get_node_chunks(db, node.id)
        context = "\n\n".join(c.text for c in chunks[:20])

        goals = (node.goals or "").strip()
        goals_block = f"Goals for this section:\n{goals}\n\n" if goals else ""
        questions_block = "\n".join(f"- {q}" for q in questions)

        prompt = dedent(
            f"""
            You are a scientific writer.
            Write a detailed section titled "{node.title}".

            {goals_block}QUESTIONS TO ADDRESS:
            {questions_block}

            CONTEXT (verbatim excerpts, cite indirectly):
            {context}

            Constraints:
            - Integrate answers to the questions.
            - Be accurate and neutral.
            - No extra headings; just the prose.
            """
        ).strip()

        node.content = llm.invoke(prompt).content.strip()
        node.mark_final()

        mark_questions_consumed(db, [q.id for q in q_objs])
        db.commit()
    finally:
        db.close()
    return node


def write_summary(node: ResearchNode) -> str:
    db = SessionLocal()
    try:
        chunks = get_node_chunks(db, node.id)
        context = "\n\n".join(c.text for c in chunks[:20])
    finally:
        db.close()

    if not context.strip():
        return f"(No summary available for: {node.title})"

    prompt = f"""
        You are a scientific assistant.
        Based on the CONTEXT, write a concluding paragraph for the section titled "{node.title}".

        CONTEXT:
        {context}

        The conclusion should briefly reflect on the key findings or implications of the section.
    """
    return llm.invoke(prompt).content.strip()


def write_conclusion(node: ResearchNode) -> str:
    db = SessionLocal()
    try:
        chunks = get_node_chunks(db, node.id)
        context = "\n\n".join(c.text for c in chunks[:20])
    finally:
        db.close()

    if not context.strip():
        return f"(No conclusion available for: {node.title})"

    prompt = f"""
        You are a scientific assistant.
        Based on the CONTEXT, write a concluding paragraph for the section titled "{node.title}".

        CONTEXT:
        {context}

        The conclusion should briefly reflect on the key findings or implications of the section.
    """
    return llm.invoke(prompt).content.strip()


def write_executive_summary(tree: ResearchTree) -> str:
    llm_local = ChatOpenAI(model="gpt-4o", temperature=0)
    sections = []
    for n in tree.root_node.subnodes:
        if n.content:
            sections.append(f"- {n.title}: {n.content[:800]}")
    context = "\n".join(sections[:12])

    prompt = dedent(
        f"""
        You are a scientific writer. Draft a crisp Executive Summary (6-10 sentences)
        of the article below. Be accurate, synthetic, and non-repetitive. Avoid headings.

        ARTICLE TITLE:
        {tree.root_node.title}

        SECTION EXCERPTS:
        {context}
    """
    ).strip()
    return llm_local.invoke(prompt).content.strip()


def write_overall_conclusion(tree: ResearchTree) -> str:
    llm_local = ChatOpenAI(model="gpt-4o", temperature=0)
    bullets = []
    for n in tree.root_node.subnodes:
        if n.summary:
            bullets.append(f"- {n.title}: {n.summary}")
        elif n.conclusion:
            bullets.append(f"- {n.title}: {n.conclusion}")
        elif n.content:
            bullets.append(f"- {n.title}: {n.content[:400]}")
    context = "\n".join(bullets[:14])

    prompt = dedent(
        f"""
        You are a scientific writer. Using the following findings, write an Overall Conclusion
        (1-2 solid paragraphs) that synthesizes the main insights and limitations, and points to
        future directions. Avoid new claims not supported by the findings.

        TITLE:
        {tree.root_node.title}

        FINDINGS:
        {context}
    """
    ).strip()
    return llm_local.invoke(prompt).content.strip()
