import argparse
import json
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import TypedDict

from llm_petrovaradinska_tvrdjava.embeddings import EmbeddingError
from llm_petrovaradinska_tvrdjava.retrieval import DenseIndex, configured_embedder, fuse_rankings
from llm_petrovaradinska_tvrdjava.reviews import ReviewMatch, load_dossiers, search_dossiers
from llm_petrovaradinska_tvrdjava.settings import Settings

CASES_PATH = Path(__file__).resolve().parents[1] / "tests/fixtures/retrieval.json"


class Case(TypedDict):
    query: str
    expected: list[str]


def observation_ids(matches: list[ReviewMatch]) -> list[str]:
    return [match.observation.observation_id for match in matches]


def report(label: str, cases: list[Case], rankings: list[list[str]]) -> bool:
    recalls: dict[int, list[float]] = {5: [], 10: []}
    reciprocal_ranks = []
    negatives = []
    for case, hits in zip(cases, rankings, strict=True):
        expected = set(case["expected"])
        if not expected:
            negatives.append(not hits)
            continue
        for k, results in recalls.items():
            results.append(len(expected.intersection(hits[:k])) / len(expected))
        rank = next((rank for rank, hit in enumerate(hits[:5], start=1) if hit in expected), 0)
        reciprocal_ranks.append(1 / rank if rank else 0.0)
    recall_5, mrr, negative_accuracy = mean(recalls[5]), mean(reciprocal_ranks), mean(negatives)
    print(f"{label} ({len(reciprocal_ranks)} positive, {len(negatives)} negative)")
    print(f"  Macro Recall@5: {recall_5:.3f} | Macro Recall@10: {mean(recalls[10]):.3f}")
    print(f"  MRR@5: {mrr:.3f} | Negative query accuracy: {negative_accuracy:.3f}")
    return recall_5 >= 1.0 and mrr >= 0.85 and negative_accuracy >= 1.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure lexical and optionally hybrid retrieval.")
    parser.add_argument(
        "--hybrid", action="store_true", help="Require a configured embedding model."
    )
    parser.add_argument(
        "--challenge", action="store_true", help="Measure harder paraphrases without a CI gate."
    )
    args = parser.parse_args()

    path = CASES_PATH.with_name("retrieval_challenge.json") if args.challenge else CASES_PATH
    cases: list[Case] = json.loads(path.read_text(encoding="utf-8"))
    dossiers = load_dossiers()
    lexical = [search_dossiers(dossiers, case["query"]) for case in cases]
    baseline_ok = report("Lexical", cases, [observation_ids(items) for items in lexical])
    if not args.hybrid:
        return int(not args.challenge and not baseline_ok)

    settings = Settings.from_environment()
    embed = configured_embedder(settings)
    if embed is None:
        parser.error("--hybrid requires FORTRESS_EMBEDDING_MODEL")
    try:
        start = perf_counter()
        index = DenseIndex.build(dossiers, embed)
        print(f"Dense index built in {perf_counter() - start:.2f}s")
        start = perf_counter()
        dense = [
            index.search(case["query"], min_similarity=settings.embedding_min_similarity)
            for case in cases
        ]
        print(f"Dense query time: {(perf_counter() - start) / len(cases):.3f}s mean")
    except EmbeddingError as error:
        parser.exit(2, f"Hybrid benchmark unavailable: {error}\n")

    report("Dense", cases, [observation_ids(items) for items in dense])
    fused = [fuse_rankings(a, b) for a, b in zip(lexical, dense, strict=True)]
    hybrid_ok = report("Hybrid", cases, [observation_ids(items) for items in fused])
    overlap = []
    for lexical_hits, dense_hits in zip(lexical, dense, strict=True):
        a, b = set(observation_ids(lexical_hits[:5])), set(observation_ids(dense_hits[:5]))
        if a or b:
            overlap.append(len(a & b) / len(a | b))
    print(f"Lexical vs dense Jaccard@5 (nonempty union): {mean(overlap) if overlap else 0:.3f}")
    return int(not args.challenge and not (baseline_ok and hybrid_ok))


if __name__ == "__main__":
    raise SystemExit(main())
