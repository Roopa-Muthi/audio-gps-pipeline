"""
Sprint 5 — Semantic cache

Avoids re-calling the LLM for transcripts that mean roughly the same thing
as one already seen (e.g. "how far to the station" vs "distance to station")
by comparing sentence embeddings with cosine similarity above a threshold.
"""
from dataclasses import dataclass

import numpy as np
from sentence_transformers import SentenceTransformer

from src.schemas import ConversationEvent


@dataclass
class CacheEntry:
    transcript: str
    embedding: np.ndarray
    event: ConversationEvent


class SemanticCache:
    def __init__(self, similarity_threshold: float = 0.90, max_entries: int = 500):
        self._model = SentenceTransformer("all-MiniLM-L6-v2")
        self._entries: list[CacheEntry] = []
        self._threshold = similarity_threshold
        self._max_entries = max_entries

    def _embed(self, text: str) -> np.ndarray:
        return self._model.encode(text, normalize_embeddings=True)

    def lookup(self, transcript: str) -> ConversationEvent | None:
        if not self._entries:
            return None
        query_vec = self._embed(transcript)
        sims = [float(np.dot(query_vec, e.embedding)) for e in self._entries]
        best_idx = int(np.argmax(sims))
        if sims[best_idx] >= self._threshold:
            return self._entries[best_idx].event
        return None

    def store(self, transcript: str, event: ConversationEvent):
        if len(self._entries) >= self._max_entries:
            self._entries.pop(0)  # simple FIFO eviction
        self._entries.append(CacheEntry(transcript=transcript, embedding=self._embed(transcript), event=event))
