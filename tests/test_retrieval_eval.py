import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from llm_petrovaradinska_tvrdjava.api import create_app

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "retrieval.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", CASES, ids=[case["query"] for case in CASES])
def test_retrieval_evaluation(case: dict[str, str | list[str]]) -> None:
    with TestClient(create_app()) as client:
        result = client.get("/api/v1/review-search", params={"q": str(case["query"])})
        assert result.status_code == 200
        hits = [match["observation"]["observation_id"] for match in result.json()]
        expected = case["expected"]
        if expected:
            assert set(expected) <= set(hits[:5])
        else:
            assert hits == []
            response = client.post("/api/v1/answers", json={"question": case["query"]})
            assert response.status_code == 200
            assert response.json()["status"] == "insufficient_evidence"
