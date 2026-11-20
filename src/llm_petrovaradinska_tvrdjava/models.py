from datetime import date
from decimal import Decimal
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

Text = Annotated[str, Field(min_length=1)]
RECORD_ID_PATTERN = r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$"
RecordId = Annotated[str, Field(pattern=RECORD_ID_PATTERN)]
Confidence = Literal["low", "medium", "high", "unassessed"]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Place(Record):
    original_name: Text | None = None
    modern_name: Text


class TemporalInterval(Record):
    original_expression: Text | None = None
    start_year: int | None = None
    end_year: int | None = None
    calendar: Literal["gregorian", "julian", "hijri", "astronomical", "bp", "other", "unknown"] = (
        "unknown"
    )
    approximate: bool = False

    @model_validator(mode="after")
    def check_interval(self) -> Self:
        if self.start_year is None and self.end_year is None and not self.original_expression:
            raise ValueError("Give a year boundary or the original date expression")
        if self.start_year is not None and self.end_year is not None:
            if self.start_year > self.end_year:
                raise ValueError("Year boundaries must be ordered numerically")
        return self


class Source(Record):
    source_id: RecordId
    bibliography: Text
    title: Text
    author_or_institution: Text
    creation_date: TemporalInterval | None = None
    publication_year: int | None = None
    edition_or_translation: Text | None = None
    source_type: Literal[
        "archival_document",
        "research",
        "map",
        "material_find",
        "oral_history",
        "book",
        "press",
        "web",
        "other",
    ]
    source_class: Literal["primary", "secondary"]
    use: Literal["evidence", "discovery_only"]
    language: Text
    script: Text
    country: Text | None = None
    archive: Text | None = None
    tradition: Text | None = None
    url: HttpUrl | None = None
    doi: Text | None = None
    isbn: Text | None = None
    archival_reference: Text | None = None
    accessed_on: date | None = None
    availability: Literal["online", "restricted", "onsite", "unavailable", "unknown"]
    copyright_status: Literal["public_domain", "open_license", "copyrighted", "unknown"]
    places: list[Place] = Field(default_factory=list)
    historical_period: Text | None = None
    actors: list[Text] = Field(default_factory=list)
    author_position_and_interest: Text | None = None
    proximity_to_event: Text | None = None
    ocr_status: Literal["not_applicable", "pending", "raw", "checked", "unknown"]
    ocr_quality_notes: Text | None = None
    reliability_notes: Text | None = None
    local_path: Text | None = None
    lawful_access_basis: Text | None = None

    @model_validator(mode="after")
    def check_provenance(self) -> Self:
        if not (self.country or self.archive or self.tradition):
            raise ValueError("Give a country, archive, or tradition of origin")
        if not (self.url or self.doi or self.isbn or self.archival_reference):
            raise ValueError("Give a URL, DOI, ISBN, or archival reference")
        if self.source_class == "primary" and not (
            self.author_position_and_interest and self.proximity_to_event
        ):
            raise ValueError("Primary sources need author context and proximity to the event")
        if self.ocr_status in {"raw", "checked"} and not self.ocr_quality_notes:
            raise ValueError("Raw and checked OCR need quality notes")
        if self.local_path is not None:
            path = PurePosixPath(self.local_path)
            if (
                path.parts[:2] != ("data", "documents")
                or len(path.parts) < 3
                or ".." in path.parts
                or any(character in self.local_path for character in '\\:<>|"?*\x00')
            ):
                raise ValueError("Local paths must be relative files under data/documents/")
            if not self.lawful_access_basis:
                raise ValueError("Document how the local copy was lawfully acquired")
        return self


class Evidence(Record):
    source_id: RecordId
    locator_kind: Literal["page", "folio", "archival_unit", "section", "other", "unavailable"]
    locator: Text
    passage_kind: Literal["quotation", "paraphrase"]
    passage: Text
    passage_language: Text | None = None
    transcription: Literal["original_checked", "unverified_ocr", "unverified"]


class Estimate(Record):
    value: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    unit: Text
    counted_population: Text
    counting_definition: Text
    approximate: bool = False


class Review(Record):
    checked_on: date
    reviewer: Text


class Claim(Record):
    claim_id: RecordId
    text: Text
    topic: Text
    event_interval: TemporalInterval | None = None
    location: Place
    evidence: Evidence
    status: Literal["confirmed", "probable", "disputed", "refuted", "unknown"]
    confidence: Confidence = "unassessed"
    supporting_evidence: list[Evidence] = Field(default_factory=list)
    contradicting_evidence: list[Evidence] = Field(default_factory=list)
    disagreement_notes: Text | None = None
    review: Review | None = None
    estimate: Estimate | None = None

    @model_validator(mode="after")
    def check_assessment(self) -> Self:
        if self.status != "unknown" and (self.review is None or self.confidence == "unassessed"):
            raise ValueError("An assessed claim needs an expert review and confidence")
        if self.status == "refuted" and not self.contradicting_evidence:
            raise ValueError("A refuted claim needs contradicting evidence")
        if self.status == "disputed" and not (
            self.supporting_evidence and self.contradicting_evidence
        ):
            raise ValueError("A disputed claim needs explicit evidence on both sides")
        if self.contradicting_evidence and not self.disagreement_notes:
            raise ValueError("Explain the disagreement when contrary evidence is recorded")
        return self


class Catalog(Record):
    schema_version: Literal[1]
    sources: list[Source]
    claims: list[Claim]

    @model_validator(mode="after")
    def check_references(self) -> Self:
        sources = {source.source_id: source for source in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("Duplicate source_id")
        if len({claim.claim_id for claim in self.claims}) != len(self.claims):
            raise ValueError("Duplicate claim_id")

        for claim in self.claims:
            passages = [claim.evidence, *claim.supporting_evidence, *claim.contradicting_evidence]
            for passage in passages:
                source = sources.get(passage.source_id)
                context = f"{claim.claim_id} / {passage.source_id}"
                if source is None:
                    raise ValueError(f"{context}: unknown source_id")
                if source.use == "discovery_only":
                    raise ValueError(f"{context}: discovery-only source cannot be evidence")
                if claim.status != "unknown" and passage.transcription != "original_checked":
                    raise ValueError(f"{context}: assessed claims require checked passages")
        return self
