import json
from functools import partial

import httpx
import pytest
from fastapi.testclient import TestClient

from llm_petrovaradinska_tvrdjava.answers import AnswerReference, DraftAnswer
from llm_petrovaradinska_tvrdjava.api import create_app
from llm_petrovaradinska_tvrdjava.embeddings import EmbeddingError, embed_with_ollama
from llm_petrovaradinska_tvrdjava.retrieval import DenseIndex, fuse_rankings
from llm_petrovaradinska_tvrdjava.reviews import iter_review_matches, load_dossiers
from llm_petrovaradinska_tvrdjava.settings import Settings


def test_rrf_promotes_shared_results_and_keeps_distinct_sources() -> None:
    first, shared, other = [
        row
        for row in iter_review_matches(load_dossiers())
        if row.observation.observation_id.startswith("artillery-")
    ]
    assert fuse_rankings([first, shared, first], [other, shared]) == [shared, first, other]


def test_hybrid_uses_dense_match_preserves_lexical_review_and_filters_weak_hits() -> None:
    indexed = 0

    def embed(texts: list[str]) -> list[list[float]]:
        nonlocal indexed
        if len(texts) > 1:
            indexed += 1
            return [[1.0, 0.0] if "Oko 100 zaplenjenih" in doc else [0.0, 1.0] for doc in texts]
        return [[1.0, 0.0]] if texts == ["Unfamiliar paraphrase"] else [[-1.0, -1.0]]

    calls = []

    def generate(question: str, references: list[AnswerReference]) -> DraftAnswer:
        calls.append([r.match.observation.observation_id for r in references])
        return DraftAnswer(claims=[])

    with TestClient(create_app(generator=generate, embedder=embed, settings=Settings())) as client:
        assert client.get("/ready").json()["retrieval"] == "hybrid"
        request = {"question": "Unfamiliar paraphrase"}
        assert client.get("/api/v1/review-search", params={"q": request["question"]}).json() == []
        reply = client.post("/api/v1/answers", json=request)
        assert reply.status_code == 200
        assert reply.headers["X-Fortress-Retrieval"] == "hybrid"
        assert (
            client.post("/api/v1/answers", json={"question": "Alien orbit"}).json()["status"]
            == "insufficient_evidence"
        )
    assert indexed == 1
    assert calls == [["artillery-eugene"]]


@pytest.mark.parametrize("failure_at_startup", [True, False])
def test_embedding_failure_degrades_to_lexical(failure_at_startup: bool) -> None:
    called = False

    def embed(texts: list[str]) -> list[list[float]]:
        if failure_at_startup or len(texts) == 1:
            raise EmbeddingError("unavailable")
        return [[1.0] for _ in texts]

    def generate(question: str, references: list[AnswerReference]) -> DraftAnswer:
        nonlocal called
        called = True
        assert references[0].match.observation.observation_id.startswith("artillery-")
        return DraftAnswer(claims=[])

    with TestClient(create_app(generator=generate, embedder=embed, settings=Settings())) as client:
        ready = client.get("/ready").json()["retrieval"]
        assert ready == ("lexical_fallback" if failure_at_startup else "hybrid")
        result = client.post("/api/v1/answers", json={"question": "Topova 1716"})
        assert result.status_code == 200
        assert result.headers["X-Fortress-Retrieval"] == "lexical_fallback"
    assert called


@pytest.mark.parametrize("bad", [[], [[1.0]], [[0.0]], [[float("inf")]]])
def test_bad_index_rejected(bad: list[list[float]]) -> None:
    with pytest.raises(EmbeddingError):
        DenseIndex.build(load_dossiers(), lambda _: bad)


def test_changed_embedding_dimensions_are_rejected() -> None:
    dossiers = load_dossiers()
    with pytest.raises(EmbeddingError, match="dimensions changed"):
        DenseIndex.build(dossiers, lambda texts: [[1.0]] + [[1.0, 0.0]] * (len(texts) - 1))
    index = DenseIndex.build(
        dossiers, lambda texts: [[1.0, 0.0]] * len(texts) if len(texts) > 1 else [[1.0]]
    )
    with pytest.raises(EmbeddingError, match="index dimensions"):
        index.search("query", min_similarity=0.65)


@pytest.mark.parametrize("mode", ["ok", "missing", "bad_vector", "bad_count", "oversize"])
def test_ollama_embeddings_are_batched_and_validated(monkeypatch, mode: str) -> None:
    from llm_petrovaradinska_tvrdjava import embeddings

    sizes = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/embed"
        body = json.loads(request.content)
        assert body["truncate"] is False
        assert body["model"] == "example"
        sizes.append(len(body["input"]))
        if mode == "missing":
            return httpx.Response(404)
        if mode == "bad_vector":
            return httpx.Response(200, json={"embeddings": [["text"]]})
        if mode == "bad_count":
            return httpx.Response(200, json={"embeddings": []})
        if mode == "oversize":
            return httpx.Response(200, content=b" " * (embeddings.MAX_EMBEDDING_RESPONSE + 1))
        return httpx.Response(200, json={"embeddings": [[1, 0.5]] * sizes[-1], "model": "example"})

    monkeypatch.setattr(
        httpx, "Client", partial(httpx.Client, transport=httpx.MockTransport(handle))
    )
    embed = partial(embed_with_ollama, "example", base_url="http://test", timeout=1)
    if mode == "ok":
        assert embed(["sample"] * 17) == [[1, 0.5]] * 17
        assert sizes == [16, 1]
    else:
        with pytest.raises(EmbeddingError):
            embed(["sample"])
