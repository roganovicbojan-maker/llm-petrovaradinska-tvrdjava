from os import environ
from typing import Self

from dotenv import dotenv_values
from pydantic import BaseModel


class Settings(BaseModel):
    debug: bool = False

    @classmethod
    def from_environment(cls) -> Self:
        file_values = dotenv_values(".env", interpolate=False)
        debug = environ.get("FORTRESS_DEBUG", file_values.get("FORTRESS_DEBUG"))
        return cls.model_validate({"debug": debug} if debug is not None else {})
