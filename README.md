# Petrovaradin Fortress LLM

A Python and FastAPI research tool for Petrovaradin and its fortress. Search five historical dossiers, compare accounts, and follow claims to their sources and locators. Optional local generation uses retrieved evidence and checks its citations and numerical statements.

## Quick start

Use Python 3.12 to match CI. In PyCharm's Git Bash terminal, run these commands from the repository root. If you already have a working project environment, start with the installation command.

```bash
python --version
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev,pdf]"
./.venv/Scripts/python.exe tools/validate_catalog.py
./.venv/Scripts/python.exe -m uvicorn llm_petrovaradinska_tvrdjava.api:create_app --factory --host 127.0.0.1 --port 8000
```

Check that the first command reports Python 3.12 before creating the environment. If the existing environment uses a different Python version or contains incompatible packages, create a fresh environment with a known Python 3.12 interpreter and select it in PyCharm. On macOS and Linux, use `./.venv/bin/python` in place of `./.venv/Scripts/python.exe`. In PowerShell, use `.\.venv\Scripts\python.exe`. In PyCharm, select the same interpreter in **Settings → Project → Python Interpreter**. To run from the IDE, create a Python run configuration with module name `uvicorn`, the arguments above, and the repository root as the working directory.

If pip reports that `validate-catalog.exe` was installed outside `PATH`, the command above still works with the project interpreter. Confirm the interpreter and package installation with `./.venv/Scripts/python.exe -m pip --version`.

Open [the dossiers](http://127.0.0.1:8000/reviews), [API documentation](http://127.0.0.1:8000/docs), or [the health endpoint](http://127.0.0.1:8000/health). Browsing and lexical search work without Ollama or credentials.

| Dossier | What you can inspect |
| --- | --- |
| [Palaeolithic finds](http://127.0.0.1:8000/reviews/petrovaradin-paleolit) | Dating of archaeological layers and the limits of evidence for continuous settlement. |
| [1694 siege](http://127.0.0.1:8000/reviews/petrovaradin-opsada-1694) | A Habsburg plan, an edition of an Ottoman chronicle, and a Hungarian diary accessed through translation. |
| [1716 battle](http://127.0.0.1:8000/reviews/petrovaradin-1716) | The date and location, artillery counts, and casualty estimates. |
| [1753–1754 construction](http://127.0.0.1:8000/reviews/petrovaradin-gradnja-1753-1754) | Proposed and reported work and the dating of the Belgrade Gate. |
| [Franciscan monastery and military hospital](http://127.0.0.1:8000/reviews/petrovaradin-samostan-sv-franje) | Construction phases and later uses of the monastery and church. |

Use `GET /api/v1/review-search?q=...` for ranked observations and `GET /api/v1/reviews/{dossier_id}` for a full dossier. Historical records and regression queries are multilingual. Original titles, transcriptions, documented place names, and source quotations remain in their recorded language.

## Local RAG answers

Install [Ollama](https://ollama.com/download), start its service, and configure a local model.

```bash
ollama pull qwen3:4b
export FORTRESS_OLLAMA_MODEL=qwen3:4b
./.venv/Scripts/python.exe -m uvicorn llm_petrovaradinska_tvrdjava.api:create_app --factory
```

You can also set variables in a local `.env` file. Use `FORTRESS_OLLAMA_BASE_URL` and `FORTRESS_OLLAMA_TIMEOUT` to change the default service address or timeout. Set `FORTRESS_OLLAMA_VERIFIER_MODEL` to use a separate model for verification. The configured generation model serves both calls by default.

Use **Ask about the fortress** on the review page, or send `POST /api/v1/answers` with `{"question":"How many cannons were captured at Peterwardein in 1716?"}`. The generator responds in the language of the question. The API checks attribution and numerical support, then asks a verifier whether the evidence supports the full claim and addresses the question. Editorial and expert reviews are recorded separately in the catalog.

### Optional hybrid retrieval

```bash
ollama pull bge-m3
export FORTRESS_EMBEDDING_MODEL=bge-m3
export FORTRESS_EMBEDDING_TIMEOUT=30
./.venv/Scripts/python.exe tools/evaluate_retrieval.py --hybrid
./.venv/Scripts/python.exe tools/evaluate_retrieval.py --hybrid --challenge
```

Run both modes with the same generator and verifier to compare answer outcomes.

```bash
./.venv/Scripts/python.exe tools/evaluate_generation.py --models qwen3:4b --retrieval lexical --challenge
./.venv/Scripts/python.exe tools/evaluate_generation.py --models qwen3:4b --retrieval hybrid --challenge
```

The evaluation reports citation IDs, abstentions, errors, and latency. Historical accuracy still requires reviewing the answer against its sources.

## Editorial workflow

See [PDF ingestion and review](docs/pdf-ingestion.md) for page-level extraction, OCR preparation, and local claim drafts.

Use `verified` when an editor has checked how an observation was recorded and attributed. Use `needs_context` when its scope or interpretation still needs investigation.

```bash
./.venv/Scripts/python.exe tools/review_comparison.py artillery-nusretname \
  --verdict needs_context --reviewer "Editor name" --date 2026-11-19 \
  --note "Check what the figure on folio 315b includes."
```

Review the catalog diff before committing and restart the app to reload the catalog.

## Checks

```bash
./.venv/Scripts/python.exe -m pytest
./.venv/Scripts/python.exe -m ruff check .
./.venv/Scripts/python.exe -m ruff format --check .
./.venv/Scripts/python.exe -m mypy src
./.venv/Scripts/python.exe tools/validate_catalog.py
./.venv/Scripts/python.exe tools/evaluate_retrieval.py
```

The validator also accepts a path to an alternative catalog. After dependency installation, the default test suite runs without external API calls.

## Documentation

- [Vision](docs/vision.md)
- [Architecture and operations](docs/architecture.md)
- [Research methodology](docs/research-methodology.md)
- [Future integration with Petrovaradin.info](docs/integration-petrovaradin-info.md)
- [Architecture decisions](docs/decisions/)
- [Data and catalog](data/README.md)

## License

Code and original project documentation are distributed under the [MIT License](LICENSE). Original project metadata is available under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See [data rights](data/README.md) for historical materials and third-party content.
