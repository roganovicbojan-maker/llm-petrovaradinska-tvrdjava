import argparse
from time import perf_counter

from fastapi.testclient import TestClient

from llm_petrovaradinska_tvrdjava.api import create_app
from llm_petrovaradinska_tvrdjava.settings import Settings

CASES: tuple[tuple[str, frozenset[str]], ...] = (
    ("Sta je predlozeno za 1754?", frozenset({"plan-proposed-1754"})),
    ("Koliko je topova Eugen prijavio kao zaplenjene 1716?", frozenset({"artillery-eugene"})),
    (
        "Koje se procene gubitaka Osmanlija razlikuju u studiji Karagoza o bici 1716?",
        frozenset({"battle-losses-ottoman-karagoz", "battle-losses-ottoman-browne"}),
    ),
    ("Who built the fortress?", frozenset()),
    ("Ko je komandovao svemirskom flotom kod Petrovaradina?", frozenset()),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare local Ollama models on fixed API cases.")
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--verifier-model", help="Keep the same verifier across all models.")
    parser.add_argument("--timeout", type=float, help="Override the Ollama network timeout.")
    args = parser.parse_args()
    if args.timeout is not None and not 0 < args.timeout < float("inf"):
        parser.error("--timeout must be a positive finite number")
    defaults = Settings.from_environment()
    failures = 0
    for model in args.models:
        settings = defaults.model_copy(
            update={
                "ollama_model": model,
                "ollama_verifier_model": args.verifier_model or defaults.ollama_verifier_model,
                "ollama_timeout": args.timeout or defaults.ollama_timeout,
            }
        )
        passed = 0
        with TestClient(create_app(settings=settings)) as client:
            for index, (question, expected) in enumerate(CASES, start=1):
                start = perf_counter()
                response = client.post("/api/v1/answers", json={"question": question})
                body = response.json()
                references = {
                    item["match"]["observation"]["observation_id"]
                    for item in body.get("references", [])
                }
                if expected:
                    match = body.get("status") == "answered" and expected <= references
                else:
                    match = body.get("status") == "insufficient_evidence"
                passed += int(match)
                failures += int(not match)
                outcome = "pass" if match else "fail"
                status = body.get("status", body.get("detail", "unknown"))
                print(
                    f"{model} #{index} {outcome} HTTP {response.status_code} "
                    f"{status} {perf_counter() - start:.1f}s {sorted(references)}",
                    flush=True,
                )
        print(f"{model}: {passed}/{len(CASES)} cases passed", flush=True)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
