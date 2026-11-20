import json
from typing import Annotated

import httpx
from pydantic import Field, StrictFloat

from .models import Record

MAX_EMBEDDING_RESPONSE = 4 * 1024 * 1024
MAX_BATCH_SIZE = 16


class EmbeddingError(Exception):
    """The embedding service failed or returned invalid vectors."""


class EmbeddingResponse(Record):
    embeddings: list[list[Annotated[StrictFloat, Field(allow_inf_nan=False)]]]

    # Ollama also returns timing and model metadata.
    model_config = {"extra": "ignore"}


def embed_with_ollama(
    model: str, texts: list[str], *, base_url: str, timeout: float
) -> list[list[float]]:
    vectors: list[list[float]] = []
    try:
        with httpx.Client(base_url=base_url, timeout=timeout, trust_env=False) as client:
            for start in range(0, len(texts), MAX_BATCH_SIZE):
                batch = texts[start : start + MAX_BATCH_SIZE]
                payload = bytearray()
                with client.stream(
                    "POST", "api/embed", json={"model": model, "input": batch, "truncate": False}
                ) as response:
                    response.raise_for_status()
                    for chunk in response.iter_bytes(chunk_size=8192):
                        payload.extend(chunk)
                        if len(payload) > MAX_EMBEDDING_RESPONSE:
                            raise EmbeddingError("Embedding response exceeded the size limit")
                parsed = EmbeddingResponse.model_validate(json.loads(payload))
                if len(parsed.embeddings) != len(batch):
                    raise EmbeddingError("Embedding response does not match input count")
                vectors.extend(parsed.embeddings)
    except (httpx.HTTPError, ValueError) as error:
        raise EmbeddingError("Ollama embeddings unavailable or invalid") from error
    return vectors
