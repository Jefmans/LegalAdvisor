import json
import logging
import os
from typing import Dict, List

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


def detect_language(text: str, *, model: str = "gpt-4o-mini") -> Dict[str, object]:
    if not text or not text.strip():
        return {"code": "und", "name": "Unknown", "confidence": 0.0}

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set; language detection skipped.")
        return {"code": "und", "name": "Unknown", "confidence": 0.0}

    llm = ChatOpenAI(model=model, temperature=0, max_tokens=80)
    prompt = (
        "Detect the language of the following text. Return JSON with keys "
        "`code` (ISO 639-1), `name` (English language name), and `confidence` (0-1). "
        "If unknown, use code `und` and name `Unknown`.\n\n"
        f"TEXT:\n{text}"
    )

    response = llm.invoke(prompt).content.strip()
    data = _parse_json(response)
    code = str(data.get("code") or "und").strip()
    name = str(data.get("name") or "Unknown").strip()
    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = 0.0
    return {"code": code, "name": name, "confidence": float(confidence)}


def detect_language_from_pages(pages: List[str], max_chars: int = 4000) -> Dict[str, object]:
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
    return detect_language(sample)
