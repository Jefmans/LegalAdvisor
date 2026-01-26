# app/utils/agent/title_from_cluster.py
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

_PROMPT = PromptTemplate.from_template(
"""
You are given a cluster of related research questions:

{questions}

Write ONE concise section title (max ~6 words).
- Declarative or noun phrase, not a question
- Avoid filler words
- Title-case it
- It should look like an academic outline heading
"""
)

def title_from_cluster(cluster: list[str]) -> str:
    if not cluster:
        return "Untitled Section"
    joined = "\n".join(f"- {q}" for q in cluster)
    resp = llm.invoke(_PROMPT.format(questions=joined))
    return resp.content.strip()
