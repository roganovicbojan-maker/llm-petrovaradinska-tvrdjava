import json

from fastapi.testclient import TestClient

from llm_petrovaradinska_tvrdjava import answers
from llm_petrovaradinska_tvrdjava.answers import AnswerClaim, AnswerReference, DraftAnswer
from llm_petrovaradinska_tvrdjava.api import create_app
from llm_petrovaradinska_tvrdjava.reviews import load_dossiers, search_dossiers

CONSTRUCTION_QUESTION = "Шта је предложено за 1754?"


def test_cyrillic_question_returns_claim_and_resolved_citation() -> None:
    def generate(question: str, references: list[AnswerReference]) -> DraftAnswer:
        assert question == CONSTRUCTION_QUESTION
        assert references[0].match.observation.observation_id == "plan-proposed-1754"
        return DraftAnswer(
            claims=[AnswerClaim(text="Plan sadrži predloge radova za 1754.", evidence_ids=[1])]
        )

    with TestClient(create_app(generator=generate)) as client:
        response = client.post("/api/v1/answers", json={"question": CONSTRUCTION_QUESTION})
        page = client.get("/reviews")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["claims"][0]["evidence_ids"] == [1]
    assert len(body["references"]) == 1
    assert body["references"][0]["match"]["observation"]["via"]["source_id"] == "sajdl-2023"
    assert 'action="/api/v1/answers"' in page.text


def test_empty_retrieval_skips_model() -> None:
    def unexpected_model(question: str, references: list[AnswerReference]) -> DraftAnswer:
        raise AssertionError("The model should not be called without evidence")

    with TestClient(create_app(generator=unexpected_model)) as client:
        response = client.post(
            "/api/v1/answers", json={"question": "Koliko je bilo stanovnika u Vinči 2024?"}
        )

    assert response.status_code == 200
    assert response.json() == {"status": "insufficient_evidence", "claims": [], "references": []}


def test_out_of_set_citation_fails_closed() -> None:
    def generate(question: str, references: list[AnswerReference]) -> DraftAnswer:
        return DraftAnswer(claims=[AnswerClaim(text="Nepouzdan odgovor", evidence_ids=[999])])

    with TestClient(create_app(generator=generate)) as client:
        response = client.post("/api/v1/answers", json={"question": "Topova 1716"})

    assert response.status_code == 502
    assert "Nepouzdan odgovor" not in response.text


def test_ollama_adapter_posts_evidence_and_parses_structured_answer(monkeypatch) -> None:
    class FakeResponse:
        status = 200

        def read(self, amount: int) -> bytes:
            draft = DraftAnswer(claims=[AnswerClaim(text="Navod iz dosijea", evidence_ids=[1])])
            return json.dumps({"message": {"content": draft.model_dump_json()}}).encode()

    class FakeConnection:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            assert (host, port, timeout) == ("127.0.0.1", 11434, 90)

        def request(self, method: str, path: str, *, body: str, headers: dict) -> None:
            assert (method, path) == ("POST", "/api/chat")
            assert headers["Content-Type"] == "application/json"
            payload = json.loads(body)
            assert payload["stream"] is False
            assert payload["format"]["type"] == "object"
            message = json.loads(payload["messages"][1]["content"])
            assert message["evidence"][0]["id"] == 1
            assert "1754" in message["evidence"][0]["value"]

        def getresponse(self) -> FakeResponse:
            return FakeResponse()

        def close(self) -> None:
            pass

    monkeypatch.setattr(answers, "HTTPConnection", FakeConnection)
    matches = search_dossiers(load_dossiers(), CONSTRUCTION_QUESTION)
    result = answers.generate_with_ollama(
        "test-model", CONSTRUCTION_QUESTION, [AnswerReference(evidence_id=1, match=matches[0])]
    )

    assert result.claims[0].evidence_ids == [1]
