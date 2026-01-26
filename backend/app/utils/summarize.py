import logging
from typing import Iterable, List

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


def _batch_texts(texts: Iterable[str], max_chars: int) -> List[str]:
    batches: List[str] = []
    current: List[str] = []
    total = 0

    for text in texts:
        if not text:
            continue
        text = text.strip()
        if not text:
            continue
        if total + len(text) > max_chars and current:
            batches.append("\n\n".join(current))
            current = []
            total = 0
        current.append(text)
        total += len(text)

    if current:
        batches.append("\n\n".join(current))

    return batches


def summarize_texts(
    texts: List[str],
    *,
    model: str = "gpt-4o-mini",
    max_chars: int = 12000,
) -> str:
    if not texts:
        return ""

    llm = ChatOpenAI(model=model, temperature=0)
    batches = _batch_texts(texts, max_chars=max_chars)

    if len(batches) == 1:
        prompt = (
            "Summarize the following content into one clear, concise text. "
            "Keep it factual and coherent, avoid bullets unless necessary.\n\n"
            f"CONTENT:\n{batches[0]}"
        )
        return llm.invoke(prompt).content.strip()

    partials: List[str] = []
    for i, batch in enumerate(batches, start=1):
        prompt = (
            f"Summarize part {i}/{len(batches)} into a concise paragraph. "
            "Focus on the key facts and remove repetition.\n\n"
            f"CONTENT:\n{batch}"
        )
        partials.append(llm.invoke(prompt).content.strip())

    final_prompt = (
        "Combine the partial summaries into one clear, unified summary. "
        "Avoid repetition and keep a smooth narrative.\n\n"
        "PARTIAL SUMMARIES:\n" + "\n\n".join(partials)
    )
    return llm.invoke(final_prompt).content.strip()
