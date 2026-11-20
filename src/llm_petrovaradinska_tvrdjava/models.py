import re
from datetime import date
from decimal import Decimal
from graphlib import CycleError, TopologicalSorter
from itertools import combinations
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self

from langcodes import tag_is_valid
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, HttpUrl, model_validator

Text = Annotated[str, Field(min_length=1)]
RECORD_ID_PATTERN = r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$"
RecordId = Annotated[str, Field(pattern=RECORD_ID_PATTERN)]
Confidence = Literal["low", "medium", "high", "unassessed"]
NonnegativeDecimal = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
QUOTATION_WORD_LIMIT = 15
WORD_PATTERN = re.compile(r"[^\W_]+(?:[’'][^\W_]+)*")


def check_language(value: str) -> str:
    if "_" in value or not tag_is_valid(value):
        raise ValueError("Use a valid BCP 47 language tag")
    return value


def check_script(value: str) -> str:
    if not tag_is_valid(f"und-{value}"):
        raise ValueError("Use a registered ISO 15924 script code")
    return value


LanguageTag = Annotated[Text, AfterValidator(check_language)]
ScriptCode = Annotated[str, Field(pattern=r"^[A-Z][a-z]{3}$"), AfterValidator(check_script)]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Place(Record):
    original_name: Text | None = None
    modern_name: Text
    aliases: list[Text] = Field(default_factory=list)
    wikidata_qid: Annotated[str, Field(pattern=r"^Q[1-9][0-9]*$")] | None = None
    latitude: Annotated[float, Field(ge=-90, le=90)] | None = None
    longitude: Annotated[float, Field(ge=-180, le=180)] | None = None

    @model_validator(mode="after")
    def check_coordinates(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Give both latitude and longitude")
        return self


class TemporalInterval(Record):
    original_expression: Text | None = None
    start_year: int | None = None
    end_year: int | None = None
    calendar: Literal["gregorian", "julian", "hijri", "astronomical", "bp", "other", "unknown"] = (
        "unknown"
    )
    approximate: bool = False
    iso_start: Text | None = None
    iso_end: Text | None = None
    precision: Literal["year", "month", "day"] | None = None
    conversion_method: Text | None = None

    @model_validator(mode="after")
    def check_interval(self) -> Self:
        has_iso = self.iso_start is not None or self.iso_end is not None
        if not has_iso and self.start_year is None and self.end_year is None:
            raise ValueError("Give a numeric year or a normalized ISO boundary")
        if self.start_year is not None and self.end_year is not None:
            if self.start_year > self.end_year:
                raise ValueError("Year boundaries must be ordered numerically")
        if self.calendar in {"other", "unknown"} and (
            self.start_year is not None or self.end_year is not None
        ):
            raise ValueError("Numeric original years need a known calendar")
        if not has_iso:
            if self.precision or self.conversion_method:
                raise ValueError("Precision and conversion method require a normalized boundary")
            return self

        if self.calendar == "bp":
            raise ValueError("BP ages cannot be used as normalized ISO dates")
        if self.calendar != "gregorian" and not self.conversion_method:
            raise ValueError("Document the conversion to the Gregorian calendar")
        if self.precision is None:
            raise ValueError("Normalized boundaries need an explicit precision")
        patterns = {
            "year": r"[0-9]{4}",
            "month": r"[0-9]{4}-[0-9]{2}",
            "day": r"[0-9]{4}-[0-9]{2}-[0-9]{2}",
        }
        suffix = {"year": "-01-01", "month": "-01", "day": ""}[self.precision]
        for boundary in (self.iso_start, self.iso_end):
            if boundary is not None:
                if not re.fullmatch(patterns[self.precision], boundary):
                    raise ValueError("Normalized date must match its precision")
                date.fromisoformat(boundary + suffix)
        if self.iso_start and self.iso_end and self.iso_start > self.iso_end:
            raise ValueError("Normalized boundaries must be ordered chronologically")
        return self


class DatingInfo(Record):
    method: Text
    value: NonnegativeDecimal
    error: NonnegativeDecimal | None = None
    unit: Literal["ka", "years_bp", "cal_years_bp"]
    original_expression: Text | None = None
    approximate: bool = False


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
    source_class: Literal["primary", "secondary", "tertiary"]
    use: Literal["evidence", "discovery_only"]
    language: LanguageTag
    script: ScriptCode
    derived_from: list[RecordId] = Field(default_factory=list)
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
        if len(set(self.derived_from)) != len(self.derived_from):
            raise ValueError("Duplicate derived_from source")
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
    passage_language: LanguageTag | None = None
    transcription: Literal["original_checked", "unverified_ocr", "unverified"]


class EvidenceLink(Evidence):
    role: Literal["supports", "contradicts", "context"]


class Estimate(Record):
    value: NonnegativeDecimal | None = None
    low: NonnegativeDecimal | None = None
    high: NonnegativeDecimal | None = None
    unit: Text
    counted_population: Text
    counting_definition: Text
    approximate: bool = False

    @model_validator(mode="after")
    def check_bounds(self) -> Self:
        if self.low is None and self.high is None:
            if self.value is None:
                raise ValueError("Give a value or both range bounds")
        elif self.low is None or self.high is None or self.low > self.high:
            raise ValueError("Give ordered lower and upper estimate bounds")
        elif self.value is not None and not self.low <= self.value <= self.high:
            raise ValueError("The estimated value must lie within its bounds")
        return self


class Review(Record):
    checked_on: date
    reviewer: Text


class Claim(Record):
    claim_id: RecordId
    text: Text
    topic: Text
    event_interval: TemporalInterval | None = None
    dating: DatingInfo | None = None
    location: Place
    evidence: Annotated[list[EvidenceLink], Field(min_length=1)]
    status: Literal["confirmed", "probable", "disputed", "refuted", "unknown"]
    confidence: Confidence = "unassessed"
    disagreement_notes: Text | None = None
    review: Review | None = None
    estimate: Estimate | None = None

    @model_validator(mode="after")
    def check_assessment(self) -> Self:
        if self.status != "unknown" and (self.review is None or self.confidence == "unassessed"):
            raise ValueError("An assessed claim needs an expert review and confidence")
        roles = {link.role for link in self.evidence}
        if self.status == "probable" and "supports" not in roles:
            raise ValueError("A probable claim needs supporting evidence")
        if self.status == "refuted" and "contradicts" not in roles:
            raise ValueError("A refuted claim needs contradicting evidence")
        if self.status == "disputed" and not {"supports", "contradicts"} <= roles:
            raise ValueError("A disputed claim needs explicit evidence on both sides")
        if "contradicts" in roles and not self.disagreement_notes:
            raise ValueError("Explain the disagreement when contrary evidence is recorded")
        return self


class Catalog(Record):
    schema_version: Literal[2]
    sources: list[Source]
    claims: list[Claim]

    @model_validator(mode="after")
    def check_references(self) -> Self:
        sources = {source.source_id: source for source in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("Duplicate source_id")
        if len({claim.claim_id for claim in self.claims}) != len(self.claims):
            raise ValueError("Duplicate claim_id")

        for source in self.sources:
            for parent in source.derived_from:
                if parent not in sources:
                    raise ValueError(f"{source.source_id}: unknown derived_from source {parent}")

        graph = TopologicalSorter({key: source.derived_from for key, source in sources.items()})
        roots: dict[str, set[str]] = {}
        try:
            for key in graph.static_order():
                parents = sources[key].derived_from
                roots[key] = (
                    set().union(*(roots[parent] for parent in parents)) if parents else {key}
                )
        except CycleError as exc:
            chain = " -> ".join(exc.args[1])
            raise ValueError(f"Source provenance cycle: {chain}") from exc

        for claim in self.claims:
            supporting_roots = []
            for passage in claim.evidence:
                source = sources.get(passage.source_id)
                context = f"{claim.claim_id} / {passage.source_id}"
                if source is None:
                    raise ValueError(f"{context}: unknown source_id")
                if source.use == "discovery_only":
                    raise ValueError(f"{context}: discovery-only source cannot be evidence")
                if claim.status != "unknown" and passage.transcription != "original_checked":
                    raise ValueError(f"{context}: assessed claims require checked passages")
                if (
                    passage.passage_kind == "quotation"
                    and source.copyright_status not in {"public_domain", "open_license"}
                    and len(WORD_PATTERN.findall(passage.passage)) > QUOTATION_WORD_LIMIT
                ):
                    raise ValueError(f"{context}: quotation exceeds {QUOTATION_WORD_LIMIT} words")
                lineage = roots[passage.source_id]
                if passage.role == "supports" and all(
                    sources[root].use == "evidence" for root in lineage
                ):
                    supporting_roots.append(lineage)
            if claim.status == "confirmed" and not any(
                left.isdisjoint(right) for left, right in combinations(supporting_roots, 2)
            ):
                raise ValueError(f"{claim.claim_id}: confirmed needs two independent root sources")
        return self
