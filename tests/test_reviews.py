from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from llm_petrovaradinska_tvrdjava.api import app
from llm_petrovaradinska_tvrdjava.review_page import render_dossier
from llm_petrovaradinska_tvrdjava.reviews import Dossier, load_demo_dossier
from tools.review_comparison import main

DOSSIER_ID = "petrovaradin-1716"


def test_review_keeps_different_source_values_and_provenance() -> None:
    with TestClient(app) as client:
        response = client.get(f"/api/v1/reviews/{DOSSIER_ID}")
        page = client.get(f"/reviews/{DOSSIER_ID}")
        missing = client.get("/reviews/unknown")

    assert response.status_code == page.status_code == 200
    assert missing.status_code == 404
    agreement, artillery = response.json()["comparisons"]
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


def test_editor_can_record_a_review_without_changing_the_observation(tmp_path: Path) -> None:
    path = tmp_path / "review.json"
    dossier = load_demo_dossier()
    path.write_text(dossier.model_dump_json(), encoding="utf-8")

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

    updated = Dossier.model_validate_json(path.read_bytes())
    row = updated.comparisons[1].observations[1]
    assert row.value == dossier.comparisons[1].observations[1].value
    assert row.review is not None
    assert row.review.verdict == "needs_context"
    assert "&lt;Check folio&gt;" in render_dossier(updated)


def test_construction_dossier_and_search_share_the_public_review_routes() -> None:
    dossier_id = "petrovaradin-gradnja-1753-1754"
    with TestClient(app) as client:
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
