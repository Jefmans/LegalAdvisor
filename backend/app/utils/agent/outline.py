from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from app.models.outline_model import Outline
from app.models.research_tree import ResearchTree

def generate_outline_from_tree(tree: ResearchTree) -> Outline:
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    parser = PydanticOutputParser(pydantic_object=Outline)

    # Collect all chunk texts from the hydrated tree (post-refactor safe)
    all_chunk_texts = [c.text for n in tree.all_nodes() for c in n.chunks]
    # De-dup while preserving order
    all_chunk_texts = list(dict.fromkeys(all_chunk_texts))

    # Collect all questions already attached across the tree
    subquestions = []
    for n in tree.all_nodes():
        subquestions.extend(n.questions or [])
    subquestions = list(dict.fromkeys(q.strip() for q in subquestions if q and q.strip()))

    query = tree.query

    prompt = PromptTemplate(
        template="""
            You are a scientific writer assistant. Create a full outline for a scientific article
            based on the main question, subquestions and context below.

            MAIN QUESTION:
            {query}

            SUBQUESTIONS:
            {subquestions}

            CONTEXT:
            {all_chunks}

            {format_instructions}
            """,
        input_variables=["query", "subquestions", "all_chunks"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )

    chain = prompt | llm | parser
    return chain.invoke({
        "query": query,
        "subquestions": subquestions,
        "all_chunks": all_chunk_texts
    })
