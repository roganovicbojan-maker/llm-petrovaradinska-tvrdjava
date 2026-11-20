from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from llm_petrovaradinska_tvrdjava.catalog import main
from llm_petrovaradinska_tvrdjava.models import (
    Catalog,
    Claim,
    Estimate,
    EvidenceLink,
    Place,
    Review,
    Source,
    TemporalInterval,
)

# Synthetic fixtures validate structure and stay outside the historical catalog.


@pytest.fixture
def source() -> Source:
    return Source(
        source_id="fixture-source",
        bibliography="Synthetic test record",
        title="Synthetic fixture",
        author_or_institution="Test author",
        source_type="research",
        source_class="secondary",
        use="evidence",
        language="sr",
        script="Latn",
        country="Synthetic origin",
        url="https://example.invalid/reference",
        availability="online",
        copyright_status="unknown",
        ocr_status="not_applicable",
    )


@pytest.fixture
def claim(source: Source) -> Claim:
    return Claim(
        claim_id="fixture-claim",
        text="Synthetic test assertion",
        topic="Test topic",
        event_interval=TemporalInterval(start_year=90000, calendar="bp", approximate=True),
        location=Place(original_name="Fixture old name", modern_name="Fixture modern name"),
        evidence=[
            EvidenceLink(
                role="supports",
                source_id=source.source_id,
                locator_kind="page",
                locator="42",
                passage_kind="paraphrase",
                passage="Synthetic test passage",
                transcription="original_checked",
            )
        ],
        status="unknown",
    )


def test_checked_in_catalog(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "valid" in capsys.readouterr().out


def test_cli_rejects_invalid_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{", encoding="utf-8")

    assert main([str(path)]) == 1
    assert str(path) in capsys.readouterr().err


def test_missing_source_rejected(claim: Claim) -> None:
    with pytest.raises(ValidationError, match="unknown source_id"):
        Catalog(schema_version=2, sources=[], claims=[claim])


def test_duplicate_ids_rejected(source: Source, claim: Claim) -> None:
    with pytest.raises(ValidationError, match="Duplicate source_id"):
        Catalog(schema_version=2, sources=[source, source], claims=[])

    with pytest.raises(ValidationError, match="Duplicate claim_id"):
        Catalog(schema_version=2, sources=[source], claims=[claim, claim])


def test_discovery_source_rejected(source: Source, claim: Claim) -> None:
    discovery_source = Source.model_validate({**source.model_dump(), "use": "discovery_only"})
    with pytest.raises(ValidationError, match="discovery-only"):
        Catalog(schema_version=2, sources=[discovery_source], claims=[claim])


def test_confirmed_requires_review(claim: Claim) -> None:
    with pytest.raises(ValidationError, match="expert review"):
        Claim.model_validate({**claim.model_dump(), "status": "confirmed"})


def test_raw_ocr_cannot_support_reviewed_claim(source: Source, claim: Claim) -> None:
    passage = EvidenceLink.model_validate(
        {**claim.evidence[0].model_dump(), "transcription": "unverified_ocr"}
    )
    reviewed_claim = Claim.model_validate(
        {
            **claim.model_dump(),
            "evidence": [passage],
            "status": "confirmed",
            "confidence": "high",
            "review": Review(checked_on=date(2026, 11, 19), reviewer="Test reviewer"),
        }
    )
    with pytest.raises(ValidationError, match="require checked passages"):
        Catalog(schema_version=2, sources=[source], claims=[reviewed_claim])


def test_disputed_requires_both_sides(claim: Claim) -> None:
    with pytest.raises(ValidationError, match="explicit evidence on both sides"):
        Claim.model_validate(
            {
                **claim.model_dump(),
                "status": "disputed",
                "confidence": "medium",
                "review": Review(checked_on=date(2026, 11, 19), reviewer="Test reviewer"),
            }
        )


def test_catalog_keeps_contradictory_estimates(source: Source, claim: Claim) -> None:
    other_source = Source.model_validate(
        {**source.model_dump(), "source_id": "fixture-other-source", "title": "Other fixture"}
    )
    other_passage = EvidenceLink.model_validate(
        {**claim.evidence[0].model_dump(), "source_id": other_source.source_id, "locator": "58"}
    )
    estimate = Estimate(
        value=Decimal("700"),
        unit="persons",
        counted_population="Synthetic group",
        counting_definition="Synthetic counting definition",
    )
    first_claim = Claim.model_validate(
        {
            **claim.model_dump(),
            "status": "disputed",
            "confidence": "medium",
            "review": Review(checked_on=date(2026, 11, 19), reviewer="Test reviewer"),
            "evidence": [
                claim.evidence[0],
                other_passage.model_copy(update={"role": "contradicts"}),
            ],
            "disagreement_notes": "Test sources give two counts",
            "estimate": estimate,
        }
    )
    second_claim = Claim.model_validate(
        {
            **claim.model_dump(),
            "claim_id": "fixture-other-claim",
            "evidence": [other_passage],
            "estimate": {**estimate.model_dump(), "value": "900"},
        }
    )
    catalog = Catalog(
        schema_version=2, sources=[source, other_source], claims=[first_claim, second_claim]
    )
    restored = Catalog.model_validate_json(catalog.model_dump_json())

    assert restored.claims == [first_claim, second_claim]


@pytest.mark.parametrize("path", ["data/documents/../copy.pdf", "C:/copy.pdf", "data/copy.pdf"])
def test_local_path_must_stay_in_documents(source: Source, path: str) -> None:
    with pytest.raises(ValidationError, match="relative files"):
        Source.model_validate(
            {**source.model_dump(), "local_path": path, "lawful_access_basis": "Fixture basis"}
        )


def test_local_copy_needs_lawful_access_basis(source: Source) -> None:
    with pytest.raises(ValidationError, match="lawfully acquired"):
        Source.model_validate({**source.model_dump(), "local_path": "data/documents/fixture.pdf"})


def test_primary_source_needs_context(source: Source) -> None:
    with pytest.raises(ValidationError, match="author context"):
        Source.model_validate({**source.model_dump(), "source_class": "primary"})


def test_calendar_interval_validation() -> None:
    with pytest.raises(ValidationError, match="ordered numerically"):
        TemporalInterval(start_year=1716, end_year=1694, calendar="julian")


def test_only_documented_normalization_is_allowed() -> None:
    with pytest.raises(ValidationError, match="numeric year or a normalized ISO"):
        TemporalInterval(original_expression="late in the campaign")
    with pytest.raises(ValidationError, match="Document the conversion"):
        TemporalInterval(calendar="julian", iso_start="1716-08-05", precision="day")
    with pytest.raises(ValidationError, match="day is out of range"):
        TemporalInterval(calendar="gregorian", iso_start="1716-02-30", precision="day")

    interval = TemporalInterval(
        calendar="julian",
        original_expression="25 July 1716",
        iso_start="1716-08-05",
        precision="day",
        conversion_method="Independently checked calendar conversion",
    )
    assert interval.iso_start == "1716-08-05"


@pytest.mark.parametrize(
    ("field", "value"), [("language", "xx-banana"), ("script", "foo"), ("script", "Fooo")]
)
def test_unregistered_language_and_script_are_rejected(
    source: Source, field: str, value: str
) -> None:
    with pytest.raises(ValidationError, match=field):
        Source.model_validate({**source.model_dump(), field: value})


def test_quote_limit_depends_on_source_rights(source: Source, claim: Claim) -> None:
    quoted = claim.evidence[0].model_copy(
        update={"passage_kind": "quotation", "passage": "word, " * 15 + "word"}
    )
    quoted_claim = claim.model_copy(update={"evidence": [quoted]})
    with pytest.raises(ValidationError, match="quotation exceeds 15 words"):
        Catalog(schema_version=2, sources=[source], claims=[quoted_claim])
    open_source = source.model_copy(update={"copyright_status": "open_license"})
    Catalog(schema_version=2, sources=[open_source], claims=[quoted_claim])


def test_confirmed_requires_disjoint_provenance_for_two_supports(
    source: Source, claim: Claim
) -> None:
    other = source.model_copy(update={"source_id": "other"})
    derived = source.model_copy(
        update={"source_id": "derived", "derived_from": [other.source_id, source.source_id]}
    )
    support = claim.evidence[0]
    confirmed = Claim.model_validate(
        {
            **claim.model_dump(),
            "status": "confirmed",
            "confidence": "high",
            "review": Review(checked_on=date(2026, 11, 19), reviewer="Test reviewer"),
        }
    )
    real_sources = [derived, other, source]
    overlap = support.model_copy(update={"source_id": derived.source_id})
    for evidence in ([support], [support, overlap], [overlap]):
        with pytest.raises(ValidationError, match="two independent root sources"):
            Catalog(
                schema_version=2,
                sources=real_sources,
                claims=[confirmed.model_copy(update={"evidence": evidence})],
            )
    independent = support.model_copy(update={"source_id": other.source_id})
    Catalog(
        schema_version=2,
        sources=real_sources,
        claims=[confirmed.model_copy(update={"evidence": [support, independent]})],
    )


def test_source_provenance_rejects_unknown_parents_and_cycles(source: Source) -> None:
    with pytest.raises(ValidationError, match="unknown derived_from"):
        Catalog(
            schema_version=2,
            sources=[source.model_copy(update={"derived_from": ["missing"]})],
            claims=[],
        )
    other = source.model_copy(update={"source_id": "other", "derived_from": [source.source_id]})
    cyclic = source.model_copy(update={"derived_from": [other.source_id]})
    with pytest.raises(ValidationError, match="provenance cycle"):
        Catalog(schema_version=2, sources=[cyclic, other], claims=[])


def test_unavailable_locator_requires_reason(claim: Claim) -> None:
    payload = claim.evidence[0].model_dump()
    payload["locator_kind"] = "unavailable"
    with pytest.raises(ValidationError, match="Explain why the locator is unavailable"):
        EvidenceLink.model_validate(payload)
    payload["locator_unavailable_reason"] = "Catalog scan has no folio numbers."
    assert EvidenceLink.model_validate(payload).locator_unavailable_reason


def test_gregorian_normalization_must_match_structured_input() -> None:
    with pytest.raises(ValidationError, match="year does not match"):
        TemporalInterval(calendar="gregorian", start_year=1694, iso_start="1695", precision="year")
    with pytest.raises(ValidationError, match="original expression does not match"):
        TemporalInterval(
            calendar="gregorian",
            original_expression="1694-09-22",
            iso_start="1694-09-23",
            precision="day",
        )
