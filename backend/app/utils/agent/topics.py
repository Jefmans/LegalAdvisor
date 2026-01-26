# app/utils/agent/topics.py
import numpy as np
from langchain_openai import OpenAIEmbeddings

def embed_texts(texts: list[str]) -> np.ndarray:
    emb = OpenAIEmbeddings(model="text-embedding-3-small")
    vecs = emb.embed_documents(texts)  # returns List[List[float]]
    return np.array(vecs, dtype=np.float32)

def cosine_sim_matrix(X: np.ndarray) -> np.ndarray:
    X = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-8)
    return X @ X.T

def group_semantic(items: list[str], tau: float | None = None) -> list[list[str]]:
    if not items:
        return []
    X = embed_texts(items)
    S = cosine_sim_matrix(X)

    # auto-pick tau if not provided: 75th percentile of off-diagonal sims
    if tau is None:
        off_diag = S[~np.eye(len(items), dtype=bool)]
        tau = float(np.percentile(off_diag, 75))
        tau = max(0.55, min(0.90, tau))

    clusters: list[list[int]] = []
    assigned = set()
    for i in range(len(items)):
        if i in assigned:
            continue
        cluster = [i]
        assigned.add(i)
        # greedy absorb
        for j in range(i+1, len(items)):
            if j in assigned:
                continue
            # similar to ANY item in the cluster?
            if any(S[j, k] >= tau for k in cluster):
                cluster.append(j)
                assigned.add(j)
        clusters.append(cluster)

    return [[items[i] for i in idxs] for idxs in clusters]
