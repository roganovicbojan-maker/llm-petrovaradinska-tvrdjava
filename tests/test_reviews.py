from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from llm_petrovaradinska_tvrdjava.api import create_app
from llm_petrovaradinska_tvrdjava.catalog import load_catalog
from llm_petrovaradinska_tvrdjava.models import Catalog
from llm_petrovaradinska_tvrdjava.reviews import Dossier, load_demo_dossier
from tools.review_comparison import main

DOSSIER_ID = "petrovaradin-1716"


def test_review_keeps_different_source_values_and_provenance() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/api/v1/reviews/{DOSSIER_ID}")
        page = client.get(f"/reviews/{DOSSIER_ID}")
        missing = client.get("/reviews/unknown")

    assert response.status_code == page.status_code == 200
    assert missing.status_code == 404
    agreement, artillery, map_history, losses, *_ = response.json()["comparisons"]
    assert map_history["observations"][0]["citation"]["source_id"] == "rct-rcin-727006"
    assert losses["observations"][0]["via"]["source_id"] == "karagoz-2014"
    assert len({row["value"] for row in agreement["observations"]}) == 1
    assert len({row["value"] for row in artillery["observations"]}) == 3
    osman = artillery["observations"][1]
    assert osman["citation"]["source_id"] == "nusretname"
    assert osman["via"]["source_id"] == "karagoz-2014"
    assert osman["review"] is None
    assert "160 ostavljenih topova" in page.text
    assert "Čeka proveru" in page.text


def test_bad_intermediary_is_rejected() -> None:
    payload = load_demo_dossier().model_dump(mode="json")
    payload["comparisons"][1]["observations"][1]["via"]["source_id"] = "missing"
    with pytest.raises(ValidationError, match="Unknown intermediary"):
        Dossier.model_validate(payload)


def test_disputed_claim_includes_both_sides_in_html_and_api() -> None:
    catalog = load_catalog().model_dump(mode="json")
    claim = next(item for item in catalog["claims"] if item["claim_id"] == "artillery-eugene")
    claim.update(
        status="disputed",
        confidence="medium",
        disagreement_notes="Synthetic disagreement",
        review={"reviewer": "Test reviewer", "checked_on": "2026-11-20"},
    )
    claim["evidence"][0]["transcription"] = "original_checked"
    claim["evidence"].append(
        {
            "source_id": "vienna-inventory-viii-56a",
            "locator_kind": "archival_unit",
            "locator": "Synthetic opposing locator",
            "passage_kind": "paraphrase",
            "passage": "Synthetic opposing passage",
            "role": "contradicts",
            "transcription": "original_checked",
        }
    )
    with TestClient(create_app(catalog_loader=lambda: Catalog.model_validate(catalog))) as client:
        api = client.get(f"/api/v1/reviews/{DOSSIER_ID}").json()
        html = client.get(f"/reviews/{DOSSIER_ID}").text
    row = api["comparisons"][1]["observations"][0]
    assert row["status"] == "disputed"
    assert row["estimate"]["value"] == "100"
    assert [item["role"] for item in row["evidence"]] == ["supports", "contradicts"]
    for label in ("Sporno", "Protivreči", "Synthetic opposing locator", "2026-11-20"):
        assert label in html


def test_catalog_rejects_unrelated_and_reversed_intermediary_chains() -> None:
    payload = load_catalog().model_dump(mode="json")
    Catalog.model_validate(payload)
    claim = next(item for item in payload["claims"] if item["claim_id"] == "artillery-nusretname")
    claim["evidence"][0]["via"]["source_id"] = "jokic-2011"
    with pytest.raises(ValidationError, match="Undocumented intermediary chain"):
        Catalog.model_validate(payload)
    claim["evidence"][0]["source_id"] = "karagoz-2014"
    claim["evidence"][0]["via"]["source_id"] = "nusretname"
    with pytest.raises(ValidationError, match="Undocumented intermediary chain"):
        Catalog.model_validate(payload)


def test_editor_can_record_a_review_without_changing_the_observation(tmp_path: Path) -> None:
    path = tmp_path / "review.json"
    dossier = load_demo_dossier()
    path.write_text(load_catalog().model_dump_json(), encoding="utf-8")

    assert (
        main(
            [
                "artillery-nusretname",
                "--file",
                str(path),
                "--verdict",
                "needs_context",
                "--reviewer",
                "Test reviewer",
                "--date",
                "2026-11-19",
                "--note",
                "<Check folio>",
            ]
        )
        == 0
    )

    updated = load_catalog(path)
    claim = next(item for item in updated.claims if item.claim_id == "artillery-nusretname")
    assert claim.text == dossier.comparisons[1].observations[1].value
    assert claim.editorial_review is not None
    assert claim.editorial_review.verdict == "needs_context"
    assert claim.editorial_review.note == "<Check folio>"


def test_construction_dossier_and_search_share_the_public_review_routes() -> None:
    dossier_id = "petrovaradin-gradnja-1753-1754"
    with TestClient(create_app()) as client:
        index = client.get("/reviews")
        construction = client.get(f"/api/v1/reviews/{dossier_id}")
        page = client.get(f"/reviews/{dossier_id}")
        result = client.get("/api/v1/review-search", params={"q": "Šta je predloženo za 1754?"})
        html = client.get("/reviews", params={"q": "Beogradska kapija"})
        battle = client.get("/api/v1/review-search", params={"q": "Koliko topova 1716?"})
        missing = client.get("/api/v1/review-search", params={"q": "vinčanski vodovod 2024"})

    assert index.status_code == construction.status_code == page.status_code == 200
    assert f"/reviews/{dossier_id}" in index.text
    assert "/reviews/petrovaradin-1716" in index.text
    assert "Tačna godina završetka ostaje otvorena." in page.text

    observations = construction.json()["comparisons"][0]["observations"]
    assert [row["observation_id"] for row in observations] == [
        "plan-reported-1753",
        "plan-proposed-1754",
    ]
    assert all(row["via"]["source_id"] == "sajdl-2023" for row in observations)

    first = result.json()[0]
    assert first["dossier_id"] == dossier_id
    assert first["observation"]["observation_id"] == "plan-proposed-1754"
    assert first["source"]["source_id"] == "kriegsarchiv-plan-15"
    assert first["intermediary"]["source_id"] == "sajdl-2023"
    assert f"/reviews/{dossier_id}#belgrade-gate-start" in html.text
    assert battle.json()[0]["dossier_id"] == "petrovaradin-1716"
    assert missing.json() == []


@pytest.mark.parametrize(
    "question", ["Koliko je stanovnika imao Petrovaradin 1716?", "Petrovaradin on Mars"]
)
def test_location_and_year_alone_do_not_match_an_unrelated_query(question: str) -> None:
    with TestClient(create_app()) as client:
        result = client.get("/api/v1/review-search", params={"q": question})
        answer = client.post("/api/v1/answers", json={"question": question})

    assert result.json() == []
    assert answer.status_code == 200
    assert answer.json()["status"] == "insufficient_evidence"


def test_historical_place_alias_and_mediated_sacral_evidence() -> None:
    with TestClient(create_app()) as client:
        duel = client.get("/api/v1/review-search", params={"q": "Peterwardein 1694"})
        common_name = client.get("/api/v1/review-search", params={"q": "Petrovaradin 1694"})
        icon = client.get("/api/v1/review-search", params={"q": "Marija Pomocnica"})

    assert duel.json() == common_name.json()
    assert duel.json()[0]["dossier_id"] == "petrovaradin-opsada-1694"
    assert icon.json()[0]["observation"]["citation"]["source_id"] == "matos-1987"
    assert icon.json()[0]["intermediary"]["source_id"] == "skoric-2011"


@pytest.mark.parametrize(
    ("dossier_id", "question", "observation_id"),
    [
        ("petrovaradin-paleolit", "90.000 godina 2b", "paleolit-2b-90ka"),
        ("petrovaradin-opsada-1694", "karta opsade 1694", "opsada-1694-karta-raspon"),
        (
            "petrovaradin-samostan-sv-franje",
            "vojna bolnica 1783",
            "franjevci-bolnica-1783",
        ),
    ],
)
def test_additional_dossiers_link_to_searchable_evidence(
    dossier_id: str, question: str, observation_id: str
) -> None:
    with TestClient(create_app()) as client:
        index = client.get("/reviews")
        page = client.get(f"/reviews/{dossier_id}")
        response = client.get("/api/v1/review-search", params={"q": question})

    assert index.status_code == page.status_code == response.status_code == 200
    assert f"/reviews/{dossier_id}" in index.text
    assert f'id="{observation_id}"' in page.text
    hit = next(
        item for item in response.json() if item["observation"]["observation_id"] == observation_id
    )
    assert hit["dossier_id"] == dossier_id
    assert hit["source"]["url"]
    assert hit["observation"]["citation"]["locator"]
