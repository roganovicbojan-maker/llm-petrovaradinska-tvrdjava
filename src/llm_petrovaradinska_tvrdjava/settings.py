from os import environ
from typing import Self

from dotenv import dotenv_values
from pydantic import BaseModel, Field, HttpUrl


class Settings(BaseModel):
    debug: bool = False
    ollama_model: str | None = None
    ollama_base_url: HttpUrl = HttpUrl("http://127.0.0.1:11434")
    ollama_timeout: float = Field(default=90.0, gt=0, allow_inf_nan=False)

    @classmethod
    def from_environment(cls) -> Self:
        file_values = dotenv_values(".env", interpolate=False)
        values = {}
        for field, variable in (
            ("debug", "FORTRESS_DEBUG"),
            ("ollama_model", "FORTRESS_OLLAMA_MODEL"),
            ("ollama_base_url", "FORTRESS_OLLAMA_BASE_URL"),
            ("ollama_timeout", "FORTRESS_OLLAMA_TIMEOUT"),
        ):
            value = environ.get(variable, file_values.get(variable))
            if value is not None:
                values[field] = value
        return cls.model_validate(values)
