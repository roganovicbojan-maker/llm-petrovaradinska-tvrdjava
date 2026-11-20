from functools import partial
from importlib.metadata import PackageNotFoundError, version
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .answers import (
    AnswerGenerator,
    AnswerQuestion,
    AnswerResult,
    InvalidAnswerError,
    ModelUnavailableError,
    answer_question,
    generate_with_ollama,
)
from .review_page import render_dossier, render_review_index
from .reviews import Dossier, ReviewMatch, load_dossier, load_dossiers, search_dossiers
from .settings import Settings


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


def create_app(*, generator: AnswerGenerator | None = None) -> FastAPI:
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
    app = FastAPI(title="LLM Petrovaradinska tvrđava", version=release, debug=settings.debug)

    @app.get("/health")
    def health() -> Health:
        return Health(version=release)

    @app.post("/api/v1/answers")
    def create_answer(request: AnswerQuestion) -> AnswerResult:
        matches = search_dossiers(load_dossiers(), request.question)
        if not matches:
            return AnswerResult(status="insufficient_evidence")
        if generate is None:
            raise HTTPException(status_code=503, detail="Podesi lokalni Ollama model u .env.")
        try:
            return answer_question(request.question, matches, generate)
        except ModelUnavailableError as error:
            raise HTTPException(status_code=503, detail="Lokalni model je nedostupan.") from error
        except InvalidAnswerError as error:
            raise HTTPException(status_code=502, detail="Provera citata nije prošla.") from error

    @app.get("/api/v1/review-search")
    def review_search(q: Annotated[str, Query(min_length=1, max_length=160)]) -> list[ReviewMatch]:
        return search_dossiers(load_dossiers(), q)

    @app.get("/api/v1/reviews/{dossier_id}")
    def review_data(dossier_id: str) -> Dossier:
        try:
            return load_dossier(dossier_id)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail="Review dossier not found") from error

    @app.get("/reviews", response_class=HTMLResponse)
    def review_index(q: Annotated[str, Query(max_length=160)] = "") -> str:
        dossiers = load_dossiers()
        return render_review_index(dossiers, q.strip(), search_dossiers(dossiers, q))

    @app.get("/reviews/{dossier_id}", response_class=HTMLResponse)
    def review_page(dossier_id: str) -> str:
        return render_dossier(review_data(dossier_id))

    return app
