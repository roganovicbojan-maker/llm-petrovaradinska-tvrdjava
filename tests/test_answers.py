import json
from functools import partial

import httpx
import pytest
from fastapi.testclient import TestClient

from llm_petrovaradinska_tvrdjava import answers
from llm_petrovaradinska_tvrdjava.answers import AnswerClaim, AnswerReference, DraftAnswer
from llm_petrovaradinska_tvrdjava.api import create_app
from llm_petrovaradinska_tvrdjava.reviews import load_dossiers, search_dossiers
from llm_petrovaradinska_tvrdjava.settings import Settings

CONSTRUCTION_QUESTION = "Шта је предложено за 1754?"


def test_cyrillic_question_returns_claim_and_resolved_citation() -> None:
    def generate(question: str, references: list[AnswerReference]) -> DraftAnswer:
        assert question == CONSTRUCTION_QUESTION
        assert references[0].match.observation.observation_id == "plan-proposed-1754"
        return DraftAnswer(
            claims=[
                AnswerClaim(
                    text=references[0].match.observation.value,
                    evidence_ids=[1],
                    source_id="kriegsarchiv-plan-15",
                )
            ]
        )

    with TestClient(create_app(generator=generate)) as client:
        response = client.post("/api/v1/answers", json={"question": CONSTRUCTION_QUESTION})
        page = client.get("/reviews")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["verification"] == "catalog_excerpt"
    assert body["claims"][0]["evidence_ids"] == [1]
    assert len(body["references"]) == 1
    assert body["references"][0]["match"]["observation"]["via"]["source_id"] == "sajdl-2023"
    assert 'action="/api/v1/answers"' in page.text
    assert "AI odgovor je generisan" in page.text


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ("connect", 503),
        ("timeout", 503),
        ("server-error", 503),
        ("not-json", 502),
        ("bad-structure", 502),
        ("oversize", 502),
    ],
)
def test_ollama_failure_is_mapped_to_public_status(
    monkeypatch: pytest.MonkeyPatch, failure: str, expected: int
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if failure == "connect":
            raise httpx.ConnectError("unavailable", request=request)
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        if failure == "server-error":
            return httpx.Response(500)
        if failure == "not-json":
            return httpx.Response(200, content=b"{")
        if failure == "bad-structure":
            return httpx.Response(200, json={"message": {"content": "{}"}})
        return httpx.Response(200, content=b" " * (answers.MAX_MODEL_RESPONSE + 1))

    original = httpx.Client
    monkeypatch.setattr(
        answers.httpx,
        "Client",
        partial(original, transport=httpx.MockTransport(handle)),
    )
    with TestClient(create_app(settings=Settings(ollama_model="test"))) as client:
        response = client.post("/api/v1/answers", json={"question": "Topova 1716"})
        assert response.status_code == expected
        assert response.json()["detail"]
        assert client.get("/ready").status_code == 200


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
        return DraftAnswer(
            claims=[
                AnswerClaim(
                    text="Nepouzdan odgovor", evidence_ids=[999], source_id="eugene-report-56"
                )
            ]
        )

    with TestClient(create_app(generator=generate)) as client:
        response = client.post("/api/v1/answers", json={"question": "Topova 1716"})

    assert response.status_code == 502
    assert "Nepouzdan odgovor" not in response.text


def test_ollama_adapter_posts_evidence_and_parses_structured_answer(monkeypatch) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "http://ollama.example:1234/api/chat"
        payload = json.loads(request.content)
        assert payload["stream"] is False
        assert payload["format"]["type"] == "object"
        message = json.loads(payload["messages"][1]["content"])
        assert message["evidence"][0]["id"] == 1
        assert "1754" in message["evidence"][0]["value"]
        draft = DraftAnswer(
            claims=[
                AnswerClaim(
                    text="Navod iz dosijea", evidence_ids=[1], source_id="kriegsarchiv-plan-15"
                )
            ]
        )
        return httpx.Response(200, json={"message": {"content": draft.model_dump_json()}})

    client = partial(httpx.Client, transport=httpx.MockTransport(handle))
    monkeypatch.setattr(answers.httpx, "Client", client)
    matches = search_dossiers(load_dossiers(), CONSTRUCTION_QUESTION)
    result = answers.generate_with_ollama(
        "test-model",
        CONSTRUCTION_QUESTION,
        [AnswerReference(evidence_id=1, match=matches[0])],
        base_url="http://ollama.example:1234",
        timeout=20,
    )

    assert result.claims[0].evidence_ids == [1]


def test_number_from_an_uncited_record_is_rejected() -> None:
    def generate(question: str, references: list[AnswerReference]) -> DraftAnswer:
        ids = {ref.match.observation.observation_id: ref.evidence_id for ref in references}
        assert "artillery-nusretname" in ids
        return DraftAnswer(
            claims=[
                AnswerClaim(
                    text="160 topova.",
                    evidence_ids=[ids["artillery-eugene"]],
                    source_id="eugene-report-56",
                )
            ]
        )

    with TestClient(create_app(generator=generate)) as client:
        result = client.post("/api/v1/answers", json={"question": "Topova 1716"})
    assert result.status_code == 502
    assert "160" not in result.text


@pytest.mark.parametrize(
    ("statement", "source", "records", "reaches_verifier"),
    [
        (
            "Nusretname navodi 100 topova.",
            "nusretname",
            ("artillery-nusretname", "artillery-eugene"),
            False,
        ),
        ("Nusretname navodi stotinu topova.", "nusretname", ("artillery-nusretname",), False),
        ("Eugen navodi sto šezdeset topova.", "eugene-report-56", ("artillery-eugene",), False),
        (
            "Osmanska vojska je pobedila u bici.",
            "rct-catalog-727006",
            ("battle-outcome-rct",),
            True,
        ),
    ],
)
def test_unsupported_source_claims_rejected(statement, source, records, reaches_verifier) -> None:
    matches = search_dossiers(load_dossiers(), "topovi 1716") + search_dossiers(
        load_dossiers(), "ishod bitke 1716"
    )
    seen = []

    def generate(question, references):
        ids = {ref.match.observation.observation_id: ref.evidence_id for ref in references}
        return DraftAnswer(
            claims=[
                AnswerClaim(
                    text=statement,
                    source_id=source,
                    evidence_ids=[ids[record] for record in records],
                )
            ]
        )

    def reject(checks):
        seen.extend(checks)
        return [False]

    with pytest.raises(answers.InvalidAnswerError):
        answers.answer_question("Bitka 1716", matches, generate, reject)
    assert bool(seen) is reaches_verifier


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Oko stotinu topova", {"100"}),
        ("Извор процењује око шест хиљада.", {"6000"}),
        ("30.000 i trideset hiljada", {"30000"}),
        ("сто шездесет, 3,5, −2", {"160", "3.5", "-2"}),
        ("Ne znamo što ističe.", set()),
        ("Dve stotine, hiljadu i dvesta", {"200", "1200"}),
    ],
)
def test_recognizes_serbian_numeric_forms(text, expected) -> None:
    assert answers.numeric_tokens(text) == expected


@pytest.mark.parametrize(("verdict", "expected"), [(True, 200), (False, 502), ("true", 502)])
def test_configured_ollama_verifier_is_a_separate_pass(monkeypatch, verdict, expected) -> None:
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append(payload["model"])
        message = json.loads(payload["messages"][1]["content"])
        if len(calls) == 1:
            item = next(e for e in message["evidence"] if e["source_id"] == "eugene-report-56")
            response = {
                "claims": [
                    {
                        "text": "Eugen navodi oko stotinu zaplenjenih topova.",
                        "source_id": item["source_id"],
                        "evidence_ids": [item["id"]],
                    }
                ]
            }
        else:
            check = message["checks"][0]
            assert check["question"] == "Topova 1716"
            assert any("100" in p for p in check["passages"])
            assert all("160" not in p for p in check["passages"])
            response = {"supported": [verdict]}
        return httpx.Response(200, json={"message": {"content": json.dumps(response)}})

    monkeypatch.setattr(
        answers.httpx,
        "Client",
        partial(httpx.Client, transport=httpx.MockTransport(handle)),
    )
    with TestClient(
        create_app(
            settings=Settings(
                ollama_model="writer",
                ollama_verifier_model="verifier",
            )
        )
    ) as client:
        result = client.post("/api/v1/answers", json={"question": "Topova 1716"})
    assert result.status_code == expected
    assert calls == ["writer", "verifier"]
    if verdict is True:
        assert result.json()["verification"] == "model_checked"
        assert result.json()["claims"][0]["source_id"] == "eugene-report-56"


def test_numeric_lists_dates_and_ranges() -> None:
    from llm_petrovaradinska_tvrdjava.numbers import numeric_ranges, numeric_tokens

    assert numeric_tokens("tri i četiri") == {"3", "4"}
    assert numeric_tokens("dvadeset i trideset") == {"20", "30"}
    assert numeric_tokens("sto šezdeset") == {"160"}
    assert numeric_tokens("6\u202f000–7\u202f000") == {"6000", "7000"}
    assert numeric_ranges("од сто до сто шездесет") == {("100", "160")}
    assert numeric_ranges("od 6.000 do 7.000; 1716-08-05") == {("6000", "7000")}


def test_range_cannot_be_synthesized_from_separate_quantities() -> None:
    from llm_petrovaradinska_tvrdjava.reviews import iter_review_matches

    match = next(
        row
        for row in iter_review_matches(load_dossiers())
        if row.observation.observation_id == "artillery-eugene"
    )
    row = match.observation.model_copy(update={"value": "100 topova i 160 vozila"})
    matches = [match.model_copy(update={"observation": row})]

    def generate(question: str, references: list[AnswerReference]) -> DraftAnswer:
        return DraftAnswer(
            claims=[
                AnswerClaim(
                    text="100–160 topova.",
                    evidence_ids=[1],
                    source_id="eugene-report-56",
                )
            ]
        )

    with pytest.raises(answers.InvalidAnswerError, match="unsupported range"):
        answers.answer_question("Topovi", matches, generate, lambda checks: [True])


def test_answer_preserves_estimate_scope_and_citations() -> None:
    from llm_petrovaradinska_tvrdjava.reviews import iter_review_matches

    matches = [
        match
        for match in iter_review_matches(load_dossiers())
        if match.observation.observation_id.startswith("artillery-")
    ]

    def generate(question: str, references: list[AnswerReference]) -> DraftAnswer:
        return DraftAnswer(
            claims=[
                AnswerClaim(
                    text=matches[0].observation.value,
                    source_id="eugene-report-56",
                    evidence_ids=[1],
                )
            ]
        )

    answer = answers.answer_question("Topovi 1716?", matches, generate)
    assert answer.estimate_comparisons is not None
    estimates = answer.estimate_comparisons[0].estimates
    assert [int(item.estimate.value) for item in estimates] == [100, 160, 175]
    assert len({item.citation.source_id for item in estimates}) == 3
    assert len({item.estimate.counting_definition for item in estimates}) == 3
