import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from functools import partial
from importlib.metadata import PackageNotFoundError, version
from threading import BoundedSemaphore
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ValidationError

from .answers import (
    AnswerGenerator,
    AnswerQuestion,
    AnswerResult,
    InvalidAnswerError,
    ModelUnavailableError,
    answer_question,
    generate_with_ollama,
)
from .catalog import load_catalog
from .models import Catalog
from .operations import RequestLimits
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
    settings: Settings | None = None,
    catalog_loader: Callable[[], Catalog] = load_catalog,
) -> FastAPI:
    if settings is None:
        settings = Settings.from_environment()
    generate = generator
    if generate is None and settings.ollama_model and settings.ollama_model.strip():
        generate = partial(
            generate_with_ollama,
            settings.ollama_model.strip(),
            base_url=str(settings.ollama_base_url),
            timeout=settings.ollama_timeout,
        )
    try:
        release = version("llm-petrovaradinska-tvrdjava")
    except PackageNotFoundError:
        release = "0+local"

    cached: list[Dossier] | None = None
    slots = BoundedSemaphore(settings.max_concurrent_generations)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        nonlocal cached
        try:
            cached = load_dossiers(catalog_loader())
        except (OSError, ValidationError):
            logger.exception("Catalog failed to load")
        try:
            yield
        finally:
            cached = None

    def get_dossiers() -> list[Dossier]:
        if not cached:
            raise HTTPException(status_code=503, detail="Katalog nije spreman.")
        return cached

    app = FastAPI(
        title="LLM Petrovaradinska tvrđava",
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
        return {"status": "ready", "generation_configured": generate is not None}

    @app.post("/api/v1/answers", response_model_exclude_none=True)
    def create_answer(request: AnswerQuestion) -> AnswerResult:
        matches = search_dossiers(get_dossiers(), request.question)
        if not matches:
            return AnswerResult(status="insufficient_evidence")
        if generate is None:
            raise HTTPException(status_code=503, detail="Podesi lokalni Ollama model u .env.")
        if not slots.acquire(blocking=False):
            raise HTTPException(
                status_code=503,
                detail="Model je zauzet. Pokušaj kasnije.",
                headers={"Retry-After": "1"},
            )
        try:
            return answer_question(request.question, matches, generate)
        except ModelUnavailableError as error:
            logger.warning("Ollama generation unavailable", exc_info=error)
            raise HTTPException(status_code=503, detail="Lokalni model je nedostupan.") from error
        except InvalidAnswerError as error:
            logger.warning("Ollama answer rejected")
            raise HTTPException(status_code=502, detail="Provera citata nije prošla.") from error
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
