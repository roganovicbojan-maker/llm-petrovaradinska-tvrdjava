import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient

from llm_petrovaradinska_tvrdjava.answers import AnswerReference, DraftAnswer
from llm_petrovaradinska_tvrdjava.api import create_app
from llm_petrovaradinska_tvrdjava.catalog import load_catalog
from llm_petrovaradinska_tvrdjava.models import Catalog
from llm_petrovaradinska_tvrdjava.settings import Settings


def test_catalog_loads_once_and_readiness_is_distinct_from_liveness() -> None:
    loads = 0

    def loader() -> Catalog:
        nonlocal loads
        loads += 1
        return load_catalog()

    with TestClient(create_app(catalog_loader=loader, settings=Settings())) as client:
        assert client.get("/ready").json() == {"status": "ready", "generation_configured": False}
        assert client.get("/reviews").status_code == 200
        assert client.get("/api/v1/review-search", params={"q": "1716"}).status_code == 200
    assert loads == 1

    def missing() -> Catalog:
        raise FileNotFoundError

    with TestClient(create_app(catalog_loader=missing)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503
        assert client.get("/reviews").status_code == 503


def test_rate_limit_and_body_limit(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(requests_per_minute=2, max_request_bytes=64)
    with (
        caplog.at_level(logging.INFO, logger="uvicorn.error.fortress.requests"),
        TestClient(create_app(settings=settings)) as client,
    ):
        oversize = client.post("/api/v1/answers", json={"question": "x" * 80})
        assert oversize.status_code == 413
        assert client.get("/reviews").status_code == 200
        limited = client.get("/reviews")
        assert limited.status_code == 429
        assert limited.headers["Retry-After"] == "60"
        assert client.get("/health").status_code == 200
    assert "status=413 duration_ms=" in caplog.text
    assert "status=429 duration_ms=" in caplog.text


def test_generation_capacity_is_released() -> None:
    started = Event()
    release = Event()

    def generator(question: str, evidence: list[AnswerReference]) -> DraftAnswer:
        started.set()
        assert release.wait(timeout=10)
        return DraftAnswer(claims=[])

    with (
        TestClient(create_app(generator=generator, settings=Settings())) as client,
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        request = {"question": "Koliko topova 1716?"}
        first = executor.submit(client.post, "/api/v1/answers", json=request)
        try:
            assert started.wait(timeout=5)
            response = client.post("/api/v1/answers", json=request)
            assert response.status_code == 503
            assert response.headers["Retry-After"] == "1"
        finally:
            release.set()
        assert first.result(timeout=5).status_code == 200
        assert client.post("/api/v1/answers", json=request).status_code == 200


@pytest.mark.parametrize("body", [b"{", b"{}", b'{"question":5}', b'{"question":" "}'])
def test_invalid_request_body_returns_422(body: bytes) -> None:
    with TestClient(create_app()) as client:
        result = client.post(
            "/api/v1/answers", content=body, headers={"Content-Type": "application/json"}
        )
    assert result.status_code == 422
