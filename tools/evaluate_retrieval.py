import json
from pathlib import Path
from statistics import mean
from typing import TypedDict

from llm_petrovaradinska_tvrdjava.reviews import load_dossiers, search_dossiers

CASES_PATH = Path(__file__).resolve().parents[1] / "tests/fixtures/retrieval.json"
TOP_K = 5


class Case(TypedDict):
    query: str
    expected: list[str]


def main() -> int:
    cases: list[Case] = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    dossiers = load_dossiers()
    recalls = []
    reciprocal_ranks = []
    negatives = []
    for case in cases:
        expected = set(case["expected"])
        hits = [
            item.observation.observation_id for item in search_dossiers(dossiers, case["query"])
        ]
        if not expected:
            negatives.append(not hits)
            continue
        hits = hits[:TOP_K]
        recalls.append(len(expected.intersection(hits)) / len(expected))
        rank = next((index for index, hit in enumerate(hits, start=1) if hit in expected), 0)
        reciprocal_ranks.append(1 / rank if rank else 0.0)
    recall, mrr, negative_accuracy = mean(recalls), mean(reciprocal_ranks), mean(negatives)
    print(f"Positive queries: {len(recalls)}; negative queries: {len(negatives)}")
    print(f"Macro Recall@{TOP_K}: {recall:.3f}")
    print(f"MRR@{TOP_K}: {mrr:.3f}")
    print(f"Negative query accuracy: {negative_accuracy:.3f}")
    return int(recall < 1.0 or mrr < 0.85 or negative_accuracy < 1.0)


if __name__ == "__main__":
    raise SystemExit(main())
