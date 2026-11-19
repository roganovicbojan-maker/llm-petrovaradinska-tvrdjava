from importlib.metadata import version
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from .settings import Settings


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


def create_app() -> FastAPI:
    settings = Settings.from_environment()
    release = version("llm-petrovaradinska-tvrdjava")
    app = FastAPI(title="LLM Petrovaradinska tvrđava", version=release, debug=settings.debug)

    @app.get("/health")
    def health() -> Health:
        return Health(version=release)

    return app


app = create_app()
