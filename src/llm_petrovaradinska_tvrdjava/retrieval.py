from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from math import hypot, isfinite, sumprod
from typing import Self

from .embeddings import EmbeddingError, embed_with_ollama
from .reviews import Dossier, ReviewMatch, iter_review_matches
from .settings import Settings

Embedder = Callable[[list[str]], list[list[float]]]
MAX_RESULTS = 10
RRF_CONSTANT = 60


def configured_embedder(settings: Settings) -> Embedder | None:
    model = (settings.embedding_model or "").strip()
    if not model:
        return None
    return partial(
        embed_with_ollama,
        model,
        base_url=str(settings.ollama_base_url),
        timeout=settings.embedding_timeout,
    )


def unit_vector(values: list[float]) -> tuple[float, ...]:
    norm = hypot(*values)
    if norm == 0 or not isfinite(norm):
        raise EmbeddingError("Embedding vector must have a finite, nonzero norm")
    return tuple(value / norm for value in values)


def document_text(match: ReviewMatch) -> str:
    observation = match.observation
    passages = "\n".join(
        f"{link.role} ({link.source.title}): {link.passage}" for link in observation.evidence
    )
    return "\n".join(
        (match.dossier_title, match.topic, observation.value, observation.context, passages)
    )


@dataclass(frozen=True, slots=True)
class DenseIndex:
    rows: tuple[tuple[ReviewMatch, tuple[float, ...]], ...]
    embed: Embedder

    @classmethod
    def build(cls, dossiers: list[Dossier], embed: Embedder) -> Self:
        by_id: dict[str, ReviewMatch] = {}
        for match in iter_review_matches(dossiers):
            by_id.setdefault(match.observation.observation_id, match)
        matches = tuple(by_id.values())
        vectors = [unit_vector(values) for values in embed([document_text(m) for m in matches])]
        if not vectors or len(vectors) != len(matches):
            raise EmbeddingError("Embedding index does not match the catalog")
        if any(len(vector) != len(vectors[0]) for vector in vectors):
            raise EmbeddingError("Embedding dimensions changed during indexing")
        return cls(tuple(zip(matches, vectors, strict=True)), embed)

    def search(self, query: str, *, min_similarity: float) -> list[ReviewMatch]:
        vectors = self.embed([query])
        if len(vectors) != 1:
            raise EmbeddingError("Expected a single query embedding")
        vector = unit_vector(vectors[0])
        if len(vector) != len(self.rows[0][1]):
            raise EmbeddingError("Query embedding does not match the index dimensions")
        scored = [(sumprod(vector, row), match) for match, row in self.rows]
        return [
            match
            for score, match in sorted(scored, key=lambda item: -item[0])[:MAX_RESULTS]
            if score >= min_similarity
        ]


def fuse_rankings(lexical: list[ReviewMatch], dense: list[ReviewMatch]) -> list[ReviewMatch]:
    scores: dict[str, float] = {}
    matches: dict[str, ReviewMatch] = {}
    for ranking in (lexical, dense):
        seen: set[str] = set()
        for rank, match in enumerate(ranking, start=1):
            key = match.observation.observation_id
            if key in seen:
                continue
            seen.add(key)
            matches.setdefault(key, match)
            scores[key] = scores.get(key, 0.0) + 1 / (RRF_CONSTANT + rank)
    return [
        matches[key] for key in sorted(scores, key=scores.__getitem__, reverse=True)[:MAX_RESULTS]
    ]
