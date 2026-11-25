import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from functools import partial
from importlib.metadata import PackageNotFoundError, version
from threading import BoundedSemaphore
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool

from .answers import (
    AnswerGenerator,
    AnswerQuestion,
    AnswerResult,
    AnswerVerifier,
    InvalidAnswerError,
    ModelTimeoutError,
    ModelUnavailableError,
    answer_question,
    catalog_answer,
    generate_with_ollama,
    verify_with_ollama,
)
from .catalog import load_catalog
from .embeddings import EmbeddingError
from .models import Catalog
from .operations import RequestLimits
from .retrieval import DenseIndex, Embedder, configured_embedder, fuse_rankings
from .review_page import render_dossier, render_review_index
from .reviews import Dossier, ReviewMatch, load_dossiers, search_dossiers
from .settings import Settings

logger = logging.getLogger(__name__)


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


def create_app(
    *,
    generator: AnswerGenerator | None = None,
    verifier: AnswerVerifier | None = None,
    embedder: Embedder | None = None,
    settings: Settings | None = None,
    catalog_loader: Callable[[], Catalog] = load_catalog,
) -> FastAPI:
    if settings is None:
        settings = Settings.from_environment()
    embed = embedder if embedder is not None else configured_embedder(settings)
    generate = generator
    if generate is None and settings.ollama_model and settings.ollama_model.strip():
        generate = partial(
            generate_with_ollama,
            settings.ollama_model.strip(),
            base_url=str(settings.ollama_base_url),
            timeout=settings.ollama_timeout,
        )
        if verifier is None:
            verifier = partial(
                verify_with_ollama,
                (settings.ollama_verifier_model or "").strip() or settings.ollama_model.strip(),
                base_url=str(settings.ollama_base_url),
                timeout=settings.ollama_timeout,
            )
    try:
        release = version("llm-petrovaradinska-tvrdjava")
    except PackageNotFoundError:
        release = "0+local"

    cached: list[Dossier] | None = None
    index: DenseIndex | None = None
    slots = BoundedSemaphore(settings.max_concurrent_generations)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        nonlocal cached, index
        try:
            cached = load_dossiers(catalog_loader())
        except (OSError, ValidationError):
            logger.exception("Catalog failed to load")
        if cached and embed is not None:
            try:
                index = await run_in_threadpool(DenseIndex.build, cached, embed)
            except EmbeddingError:
                logger.warning(
                    "Embedding index unavailable; using lexical retrieval", exc_info=True
                )
        try:
            yield
        finally:
            cached = None
            index = None

    def get_dossiers() -> list[Dossier]:
        if not cached:
            raise HTTPException(status_code=503, detail="The catalog is not ready.")
        return cached

    app = FastAPI(
        title="Petrovaradin Fortress LLM",
        version=release,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.add_middleware(
        RequestLimits,
        requests_per_minute=settings.requests_per_minute,
        max_request_bytes=settings.max_request_bytes,
    )

    @app.get("/health")
    def health() -> Health:
        return Health(version=release)

    @app.get("/ready")
    def readiness() -> dict[str, str | bool]:
        get_dossiers()
        status: dict[str, str | bool] = {
            "status": "ready",
            "generation_configured": generate is not None,
        }
        if embed is not None:
            status["retrieval"] = "hybrid" if index is not None else "lexical_fallback"
        return status

    @app.post("/api/v1/answers", response_model_exclude_none=True)
    def create_answer(request: AnswerQuestion, response: Response) -> AnswerResult:
        matches = search_dossiers(get_dossiers(), request.question)
        retrieval = "lexical_fallback" if embed is not None else "lexical"
        response.headers["X-Fortress-Retrieval"] = retrieval
        if not matches and index is None:
            return AnswerResult(status="insufficient_evidence")
        catalog_result = catalog_answer(request.question, matches)
        if catalog_result is not None:
            return catalog_result
        if generate is None:
            raise HTTPException(status_code=503, detail="Configure a local Ollama model in .env.")
        if not slots.acquire(blocking=False):
            raise HTTPException(
                status_code=503,
                detail="The model is busy. Try again later.",
                headers={"Retry-After": "1"},
            )
        try:
            if index is not None:
                try:
                    dense = index.search(
                        request.question, min_similarity=settings.embedding_min_similarity
                    )
                    matches = fuse_rankings(matches, dense)
                    response.headers["X-Fortress-Retrieval"] = "hybrid"
                except EmbeddingError:
                    logger.warning("Embedding query failed; using lexical retrieval", exc_info=True)
            return answer_question(request.question, matches, generate, verifier)
        except ModelTimeoutError as error:
            logger.warning("Ollama answer request timed out")
            raise HTTPException(
                status_code=503, detail="The local model did not answer in time."
            ) from error
        except ModelUnavailableError as error:
            logger.warning("Ollama generation unavailable", exc_info=error)
            raise HTTPException(
                status_code=503, detail="The local model is unavailable."
            ) from error
        except InvalidAnswerError as error:
            logger.warning("Ollama answer rejected: %s", error)
            raise HTTPException(
                status_code=502, detail="Citation or evidence validation failed."
            ) from error
        finally:
            slots.release()

    @app.get("/api/v1/review-search")
    def review_search(q: Annotated[str, Query(min_length=1, max_length=160)]) -> list[ReviewMatch]:
        return search_dossiers(get_dossiers(), q)

    @app.get("/api/v1/reviews/{dossier_id}")
    def review_data(dossier_id: str) -> Dossier:
        for dossier in get_dossiers():
            if dossier.dossier_id == dossier_id:
                return dossier
        raise HTTPException(status_code=404, detail="Review dossier not found")

    @app.get("/reviews", response_class=HTMLResponse)
    def review_index(q: Annotated[str, Query(max_length=160)] = "") -> str:
        dossiers = get_dossiers()
        return render_review_index(dossiers, q.strip(), search_dossiers(dossiers, q))

    @app.get("/reviews/{dossier_id}", response_class=HTMLResponse)
    def review_page(dossier_id: str) -> str:
        return render_dossier(review_data(dossier_id))

    return app
