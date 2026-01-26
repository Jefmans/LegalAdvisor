import logging
import os
from typing import Callable, List

import tiktoken
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

from app.models import TextChunkEmbedding


MODEL = "text-embedding-3-small"
TARGET_BATCH_TOKENS = 250_000

load_dotenv()

logger = logging.getLogger(__name__)
embedding_model = OpenAIEmbeddings(
    model=MODEL,
    openai_api_key=os.getenv("OPENAI_API_KEY"),
)

# Initialize tokenizer for the embedding model
encoding = tiktoken.encoding_for_model(MODEL)


def estimate_tokens(text: str) -> int:
    return len(encoding.encode(text))


def embed_chunks_streaming(
    chunks: List[dict],
    save_fn: Callable[[List[TextChunkEmbedding]], None],
) -> None:
    logger.info("Embedding %s chunks in token-capped batches", len(chunks))

    current_batch: List[dict] = []
    current_tokens = 0

    for chunk in chunks:
        chunk_tokens = estimate_tokens(chunk["text"])
        if current_tokens + chunk_tokens > TARGET_BATCH_TOKENS:
            _process_batch(current_batch, save_fn)
            current_batch = []
            current_tokens = 0

        current_batch.append(chunk)
        current_tokens += chunk_tokens

    if current_batch:
        _process_batch(current_batch, save_fn)

    logger.info("All chunks embedded and saved")


def _process_batch(batch: List[dict], save_fn) -> None:
    if not batch:
        return
    logger.info("Embedding batch of %s chunks", len(batch))
    texts = [c["text"] for c in batch]

    try:
        vectors = embedding_model.embed_documents(texts)
    except Exception as e:
        logger.exception("Failed to embed batch: %s", e)
        raise

    results: List[TextChunkEmbedding] = []
    for chunk, vector in zip(batch, vectors):
        results.append(
            TextChunkEmbedding(
                chunk_size=chunk["chunk_size"],
                chunk_index=chunk["chunk_index"],
                text=chunk["text"],
                pages=chunk["pages"],
                embedding=vector,
            )
        )

    save_fn(results)
    logger.info("Saved %s embedded chunks", len(results))


def embed_chunks(chunks: List[dict]) -> List[TextChunkEmbedding]:
    texts = [chunk["text"] for chunk in chunks]
    vectors = embedding_model.embed_documents(texts)

    results: List[TextChunkEmbedding] = []
    for chunk, vector in zip(chunks, vectors):
        results.append(
            TextChunkEmbedding(
                chunk_size=chunk["chunk_size"],
                chunk_index=chunk["chunk_index"],
                text=chunk["text"],
                pages=chunk["pages"],
                embedding=vector,
            )
        )
    return results
