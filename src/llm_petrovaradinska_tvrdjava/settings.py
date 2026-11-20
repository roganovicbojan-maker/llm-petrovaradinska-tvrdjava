from os import environ
from typing import Self

from dotenv import dotenv_values
from pydantic import BaseModel


class Settings(BaseModel):
    debug: bool = False
    ollama_model: str | None = None

    @classmethod
    def from_environment(cls) -> Self:
        file_values = dotenv_values(".env", interpolate=False)
        values = {}
        for field, variable in (
            ("debug", "FORTRESS_DEBUG"),
            ("ollama_model", "FORTRESS_OLLAMA_MODEL"),
        ):
            value = environ.get(variable, file_values.get(variable))
            if value is not None:
                values[field] = value
        return cls.model_validate(values)
