# Architecture

The version 2 catalog records sources, claims, evidence roles, intermediaries, and editorial assessments. Python, Pydantic, and FastAPI expose the same data as HTML and public JSON. The application validates and loads the catalog at startup. Restart the process after changing it.

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Process liveness and package version. |
| `GET /ready` | Catalog readiness and whether generation is configured. It does not ping the Ollama service. |
| `GET /reviews`, `GET /reviews/{dossier_id}` | Browse and search dossiers. |
| `GET /api/v1/review-search` | Up to ten ranked observations with evidence. |
| `GET /api/v1/reviews/{dossier_id}` | JSON dossier with evidence and catalog assessments. |
| `POST /api/v1/answers` | Optional generated answer with retrieved references. |
| `GET /docs` | OpenAPI documentation. |

Lexical retrieval normalizes Latin and Cyrillic scripts, diacritics, and recorded historical and inflected variants. `python tools/evaluate_retrieval.py` reports macro Recall@5 and Recall@10, MRR@5, and the share of negative queries without results. The regression sets cover the existing dossiers. Broader historical relevance requires an independently labeled expert corpus.

The optional hybrid mode builds an in-memory index with one vector per observation ID at startup. Ollama's `/api/embed` receives observation text, passages, and context. Retrieval compares cosine similarity against the index, drops scores below a threshold, and combines rankings with reciprocal rank fusion. Catalog links, claim statuses, and evidence roles are preserved. The initial `FORTRESS_EMBEDDING_MIN_SIMILARITY` value of 0.65 needs evaluation for each embedding model.

With no `FORTRESS_EMBEDDING_MODEL`, answers use lexical retrieval. A failed index build falls back to lexical retrieval until restart. A failed embedding query falls back for that request. `GET /ready` reports index availability if configured. Successful answer responses identify the retrieval path in `X-Fortress-Retrieval`. Dossier browsing and the review search endpoint use lexical retrieval. The CI regression suite runs without Ollama.

The generator receives observations and their evidence roles. Each claim attributes evidence IDs to a single source ID. Validation rejects references outside the retrieved set, numbers missing from the cited source, and ranges assembled from unrelated quantities. A separate model call checks whether evidence supports the full claim, its attribution and qualifications, and its relevance to the question. This produces a `model_checked` answer. A custom generator without a verifier must match a catalog excerpt and returns `catalog_excerpt`. Historical assessment and expert review are tracked separately in the catalog.

## Startup and request limits

Start the app with `uvicorn llm_petrovaradinska_tvrdjava.api:create_app --factory`. Process environment variables take precedence over `.env`. A development checkout loads the repository-root `.env`. An installed package uses the process environment or the file specified by the absolute `FORTRESS_ENV_FILE` path.

| Setting | Default and behavior |
| --- | --- |
| `FORTRESS_REQUESTS_PER_MINUTE` | A sliding window of 120 requests per process, excluding `/health` and `/ready`. Excess requests return 429. |
| `FORTRESS_MAX_REQUEST_BYTES` | 4,096 bytes for answer requests. Larger bodies return 413. Reading the body has a 10-second deadline. |
| `FORTRESS_MAX_CONCURRENT_GENERATIONS` | One concurrent generation per process. A busy service returns 503 with `Retry-After`. |
| `FORTRESS_OLLAMA_TIMEOUT` | 90 seconds for generation network operations. Unavailable models return 503 and invalid answers return 502. |

Request logs record method, status, and duration. Monitor latency and 429, 502, and 503 responses. Generation can be disabled by clearing the model setting and restarting. Before public exposure, configure a reverse proxy with TLS, connection and body-size limits, per-client limits, and a shared budget across application processes. Use authentication for private API access. Load-test the deployment and configure monitoring and alerts.

The broader corpus plan includes OCR, indexing passages from primary sources, and independent expert evaluation. See [data rights](../data/README.md) for code, metadata, and historical material.
