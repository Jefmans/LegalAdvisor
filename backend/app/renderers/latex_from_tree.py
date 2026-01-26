from __future__ import annotations

import json
import re
from typing import Any, Dict

from langchain_openai import ChatOpenAI

from app.models.research_tree import ResearchNode, ResearchTree

_LLM = ChatOpenAI(model="gpt-4o", temperature=0)

_FORBIDDEN = [
    r"\\write18",
    r"\\input\{",
    r"\\include\{",
    r"\\openout",
    r"\\read",
    r"\\csname",
    r"\\catcode",
    r"\\def",
    r"\\newcommand",
]


def _sanitize(tex: str) -> str:
    for pat in _FORBIDDEN:
        tex = re.sub(pat, "", tex, flags=re.IGNORECASE)
    return tex.strip()


def _compact_tree(tree: ResearchTree) -> Dict[str, Any]:
    def node_to_dict(n: ResearchNode, is_root: bool = False) -> Dict[str, Any]:
        out = {
            "title": n.title,
            "rank": n.rank,
            "level": n.level,
            "display_rank": n.display_rank,
            "goals": (n.goals or ""),
            "content": (n.content or ""),
            "summary": (n.summary or "") if is_root else "",
            "conclusion": (n.conclusion or "") if is_root else "",
            "questions": list(n.questions or []),
            "sources": [],
            "subnodes": [],
        }
        hints = []
        for c in (n.chunks or [])[:8]:
            hints.append({"source": c.source or "", "page": c.page})
        out["sources"] = hints

        out["subnodes"] = [node_to_dict(sn, is_root=False) for sn in (n.subnodes or [])]
        return out

    return {
        "query": tree.query,
        "root": node_to_dict(tree.root_node, is_root=True),
    }


_PROMPT = r"""
You are a LaTeX typesetter for scientific articles.

You will receive a JSON-serialized research tree with:
- A root node (the article), with nested section nodes (subsections).
- Each node has: title, rank/level, optional goals/content/summary/conclusion, optional questions,
  and optional (source,page) hints.

TASK:
Produce a single, compilable LaTeX document **including preamble** that renders this article.

STRICT RULES:
- Use this exact preamble (no extra packages, no changes):

\documentclass[11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{hyperref}
\usepackage{geometry}
\geometry{margin=1in}

- After \begin{document}:
  - Title = root title (or fallback to the query), then \maketitle
  - If root.summary is present, render a \section*{Executive Summary} with that text.
  - If root.content is present, render a \section*{Abstract} with that text.
  - Then render all sections from the tree, preserving hierarchy:
    level 1 -> \section, level 2 -> \subsection, level 3 -> \subsubsection, level >=4 -> \paragraph
  - For each non-root node, render ONLY its main prose from `content` (no per-node summary/conclusion).
  - Optionally append a footnotesize "Sources:" line from (source, page) hints.
  - If root.conclusion is present, render a \section*{Overall Conclusion} at the end.

- DO NOT use figures, tables, bibliographies, \cite, \includegraphics, or custom macros.
- Escape LaTeX special characters in prose.
- Never invent sources/pages - only use the given hints.

Now generate the full LaTeX document.

=== RESEARCH TREE JSON ===
<<<TREE_JSON>>>
"""


def to_latex_via_llm(tree: ResearchTree) -> str:
    data = _compact_tree(tree)
    tree_json = json.dumps(data, ensure_ascii=False)
    prompt = _PROMPT.replace("<<<TREE_JSON>>>", tree_json)

    tex = _LLM.invoke(prompt).content
    return _sanitize(tex)
