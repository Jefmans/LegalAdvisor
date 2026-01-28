import json
import logging
import os
from typing import Dict, List, Optional

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


def _parse_json(content: str) -> Dict[str, object]:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(content[start : end + 1])
    except Exception:
        return {}


def detect_section_patterns(
    text: str,
    *,
    language_code: Optional[str] = None,
    model: str = "gpt-4o-mini",
) -> List[str]:
    if not text or not text.strip():
        return []

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set; section detection skipped.")
        return []

    llm = ChatOpenAI(model=model, temperature=0, max_tokens=180)
    language_hint = f"Language code: {language_code}." if language_code else "Language code: unknown."
    prompt = (
        "You are analyzing a legal document sample. Identify how section headings are written.\n"
        "Return JSON: {\"patterns\": [\"Article\\\\s+\\\\d+\", \"§\\\\s*\\\\d+\"]}.\n"
        "The patterns should match heading text inside the document (no ^ or $ anchors).\n"
        "If unsure, return an empty list.\n\n"
        f"{language_hint}\n\n"
        f"SAMPLE:\n{text}"
    )

    response = llm.invoke(prompt).content.strip()
    data = _parse_json(response)
    patterns = data.get("patterns")
    if not isinstance(patterns, list):
        return []
    return [p for p in patterns if isinstance(p, str) and p.strip()]


def detect_section_patterns_from_pages(
    pages: List[str],
    *,
    language_code: Optional[str] = None,
    max_chars: int = 6000,
) -> List[str]:
    sample = ""
    for page in pages:
        if not page:
            continue
        text = page.strip()
        if not text:
            continue
        remaining = max_chars - len(sample)
        if remaining <= 0:
            break
        fragment = text[:remaining]
        sample = f"{sample}\n\n{fragment}" if sample else fragment
    return detect_section_patterns(sample, language_code=language_code)
