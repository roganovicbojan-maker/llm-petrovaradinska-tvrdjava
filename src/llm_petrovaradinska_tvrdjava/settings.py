from os import environ
from pathlib import Path
from typing import Self

from dotenv import dotenv_values
from pydantic import BaseModel, Field, HttpUrl


class Settings(BaseModel):
    debug: bool = False
    ollama_model: str | None = None
    ollama_verifier_model: str | None = None
    ollama_base_url: HttpUrl = HttpUrl("http://127.0.0.1:11434")
    ollama_timeout: float = Field(default=90.0, gt=0, allow_inf_nan=False)
    requests_per_minute: int = Field(default=120, ge=1)
    max_request_bytes: int = Field(default=4096, ge=1)
    max_concurrent_generations: int = Field(default=1, ge=1)

    @classmethod
    def from_environment(cls) -> Self:
        configured_path = environ.get("FORTRESS_ENV_FILE")
        project_root = Path(__file__).resolve().parents[2]
        if configured_path:
            env_file = Path(configured_path).expanduser()
            if not env_file.is_absolute():
                raise ValueError("FORTRESS_ENV_FILE must be an absolute path")
            if not env_file.is_file():
                raise ValueError("FORTRESS_ENV_FILE must point to a file")
        else:
            env_file = project_root / ".env"
        file_values = (
            dotenv_values(env_file, interpolate=False)
            if configured_path or (project_root / "pyproject.toml").is_file()
            else {}
        )
        values = {}
        for field, variable in (
            ("debug", "FORTRESS_DEBUG"),
            ("ollama_model", "FORTRESS_OLLAMA_MODEL"),
            ("ollama_verifier_model", "FORTRESS_OLLAMA_VERIFIER_MODEL"),
            ("ollama_base_url", "FORTRESS_OLLAMA_BASE_URL"),
            ("ollama_timeout", "FORTRESS_OLLAMA_TIMEOUT"),
            ("requests_per_minute", "FORTRESS_REQUESTS_PER_MINUTE"),
            ("max_request_bytes", "FORTRESS_MAX_REQUEST_BYTES"),
            ("max_concurrent_generations", "FORTRESS_MAX_CONCURRENT_GENERATIONS"),
        ):
            value = environ.get(variable, file_values.get(variable))
            if value is not None:
                values[field] = value
        return cls.model_validate(values)
