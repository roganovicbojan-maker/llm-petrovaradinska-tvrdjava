import re
import unicodedata
from typing import Annotated, Literal, Self

from pydantic import Field, HttpUrl, model_validator

from .catalog import load_catalog
from .models import (
    RECORD_ID_PATTERN,
    Catalog,
    Citation,
    ClaimStatus,
    Confidence,
    DatingInfo,
    Estimate,
    EvidenceLink,
    Place,
    Record,
    RecordId,
    Review,
    Source,
    SourceReview,
    TemporalInterval,
    Text,
)


class DossierSource(Record):
    source_id: RecordId
    title: Text
    tradition: Text
    kind: Literal["primary", "secondary", "map"]
    url: HttpUrl | None = None
    bibliography: Text | None = None
    edition_or_translation: Text | None = None
    publication_year: int | None = None


class DossierEvidence(EvidenceLink):
    source: DossierSource
    intermediary: DossierSource | None = None


class Observation(Record):
    observation_id: RecordId
    citation: Citation
    via: Citation | None = None
    value: Text
    context: Text
    review: SourceReview | None = None
    status: ClaimStatus = "unknown"
    confidence: Confidence = "unassessed"
    expert_review: Review | None = None
    evidence: list[DossierEvidence] = Field(default_factory=list)
    estimate: Estimate | None = None
    dating: DatingInfo | None = None
    event_interval: TemporalInterval | None = None
    location: Place | None = None
    disagreement_notes: Text | None = None


class Comparison(Record):
    topic: Text
    observations: Annotated[list[Observation], Field(min_length=1)]


class Dossier(Record):
    dossier_id: RecordId
    title: Text
    summary: Text
    sources: Annotated[list[DossierSource], Field(min_length=1)]
    comparisons: Annotated[list[Comparison], Field(min_length=1)]

    @model_validator(mode="after")
    def check_references(self) -> Self:
        sources = {source.source_id for source in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("Duplicate dossier source_id")
        observations = set()
        for comparison in self.comparisons:
            for observation in comparison.observations:
                if observation.observation_id in observations:
                    raise ValueError(f"Duplicate observation_id: {observation.observation_id}")
                observations.add(observation.observation_id)
                if observation.citation.source_id not in sources:
                    raise ValueError(f"Unknown source_id: {observation.citation.source_id}")
                if observation.via:
                    if observation.via.source_id not in sources:
                        raise ValueError(f"Unknown intermediary: {observation.via.source_id}")
                    if observation.via.source_id == observation.citation.source_id:
                        raise ValueError("A source cannot be its own intermediary")
        return self


def load_dossier(dossier_id: str) -> Dossier:
    if re.fullmatch(RECORD_ID_PATTERN, dossier_id) is None:
        raise FileNotFoundError(dossier_id)
    for dossier in load_dossiers():
        if dossier.dossier_id == dossier_id:
            return dossier
    raise FileNotFoundError(dossier_id)


def load_demo_dossier() -> Dossier:
    return load_dossier("petrovaradin-1716")


def project_source(source: Source) -> DossierSource:
    kind: Literal["primary", "secondary", "map"] = "secondary"
    if source.source_type == "map":
        kind = "map"
    elif source.source_class == "primary":
        kind = "primary"
    return DossierSource(
        source_id=source.source_id,
        title=source.title,
        tradition=source.tradition or source.author_or_institution,
        kind=kind,
        url=source.url,
        bibliography=source.bibliography,
        edition_or_translation=source.edition_or_translation,
        publication_year=source.publication_year,
    )


def load_dossiers(catalog: Catalog | None = None) -> list[Dossier]:
    if catalog is None:
        catalog = load_catalog()
    claims = {claim.claim_id: claim for claim in catalog.claims}
    sources = {source.source_id: project_source(source) for source in catalog.sources}
    dossiers = []
    for definition in catalog.dossiers:
        groups: dict[str, list[Observation]] = {}
        source_ids: dict[str, None] = {}
        for claim_id in definition.claim_ids:
            claim = claims[claim_id]
            evidence = claim.evidence[0]
            evidence_rows = []
            for item in claim.evidence:
                source_ids[item.source_id] = None
                intermediary = None
                if item.via:
                    source_ids[item.via.source_id] = None
                    intermediary = sources[item.via.source_id]
                evidence_rows.append(
                    DossierEvidence.model_validate(
                        {
                            **item.model_dump(),
                            "source": sources[item.source_id],
                            "intermediary": intermediary,
                        }
                    )
                )
            groups.setdefault(claim.topic, []).append(
                Observation(
                    observation_id=claim_id,
                    citation=Citation(source_id=evidence.source_id, locator=evidence.locator),
                    via=evidence.via,
                    value=claim.text,
                    context=evidence.passage,
                    review=claim.editorial_review,
                    status=claim.status,
                    confidence=claim.confidence,
                    expert_review=claim.review,
                    evidence=evidence_rows,
                    estimate=claim.estimate,
                    dating=claim.dating,
                    event_interval=claim.event_interval,
                    location=claim.location,
                    disagreement_notes=claim.disagreement_notes,
                )
            )
        dossiers.append(
            Dossier(
                dossier_id=definition.dossier_id,
                title=definition.title,
                summary=definition.summary,
                sources=[sources[source_id] for source_id in source_ids],
                comparisons=[
                    Comparison(topic=topic, observations=rows) for topic, rows in groups.items()
                ],
            )
        )
    return dossiers


class ReviewMatch(Record):
    dossier_id: RecordId
    dossier_title: Text
    topic: Text
    observation: Observation
    source: DossierSource
    intermediary: DossierSource | None = None


TOKEN_PATTERN = re.compile(r"[^\W_]+")
QUESTION_WORDS = {
    "je",
    "za",
    "sto",
    "sta",
    "su",
    "na",
    "iz",
    "od",
    "ko",
    "kod",
    "koje",
    "koja",
    "kako",
    "koliko",
    "kada",
    "bilo",
    "bila",
    "imao",
    "se",
    "da",
    "on",
}
SEARCH_ALIASES = {
    "peterwardein": "petrovaradin",
    "petervardein": "petrovaradin",
    "petervarad": "petrovaradin",
    "petervaradin": "petrovaradin",
    "varadin": "petrovaradin",
    "predlozeno": "predlozeni",
    "pomocnice": "pomocnica",
    "kapije": "kapija",
    "kapiju": "kapija",
    "beogradsku": "beogradska",
    "beogradske": "beogradska",
    "opatiju": "opatija",
    "gubitaka": "gubici",
    "marije": "marija",
    "sedimenta": "sediment",
    "redeponovan": "redepozicija",
    "opsade": "opsada",
    "opsadu": "opsada",
    "topovi": "topova",
    "topove": "topova",
}
QUERY_CONTEXT = {
    "petrovaradin",
    "petrovaradina",
    "petrovaradinu",
    "tvrdjava",
    "tvrdjave",
    "tvrdjavi",
}


SERBIAN_CYRILLIC = str.maketrans(
    dict(
        zip(
            "абвгдђежзијклљмнњопрстћуфхцчџш",
            (
                "a",
                "b",
                "v",
                "g",
                "d",
                "đ",
                "e",
                "ž",
                "z",
                "i",
                "j",
                "k",
                "l",
                "lj",
                "m",
                "n",
                "nj",
                "o",
                "p",
                "r",
                "s",
                "t",
                "ć",
                "u",
                "f",
                "h",
                "c",
                "č",
                "dž",
                "š",
            ),
            strict=True,
        )
    )
)


def search_terms(text: str) -> set[str]:
    normalized = unicodedata.normalize(
        "NFKD", text.casefold().translate(SERBIAN_CYRILLIC).replace("đ", "dj")
    )
    normalized = "".join(letter for letter in normalized if not unicodedata.combining(letter))
    return {
        SEARCH_ALIASES.get(word, word)
        for word in TOKEN_PATTERN.findall(normalized)
        if len(word) > 1
    } - QUESTION_WORDS


def search_dossiers(dossiers: list[Dossier], query: str) -> list[ReviewMatch]:
    terms = search_terms(query)
    if not terms:
        return []

    topical_terms = {term for term in terms - QUERY_CONTEXT if not term.isdecimal()}
    matches = []
    for dossier in dossiers:
        sources = {source.source_id: source for source in dossier.sources}
        dossier_terms = search_terms(dossier.title)
        for comparison in dossier.comparisons:
            topic_terms = search_terms(comparison.topic)
            for row in comparison.observations:
                source = sources[row.citation.source_id]
                intermediary = sources[row.via.source_id] if row.via else None
                value_terms = search_terms(row.value)
                evidence_terms = search_terms(
                    f"{row.context} {row.citation.locator} {source.title} {source.tradition}"
                )
                if source.kind == "map":
                    evidence_terms.add("karta")
                for evidence in row.evidence[1:]:
                    evidence_terms |= search_terms(
                        f"{evidence.passage} {evidence.locator} {evidence.source.title}"
                    )
                covered_topics = topical_terms & (
                    value_terms | topic_terms | evidence_terms | dossier_terms
                )
                if topical_terms and len(covered_topics) <= len(topical_terms) // 2:
                    continue
                score = (
                    4 * len(terms & value_terms)
                    + 2 * len(terms & (topic_terms | evidence_terms))
                    + len(terms & dossier_terms)
                )
                if score:
                    match = ReviewMatch(
                        dossier_id=dossier.dossier_id,
                        dossier_title=dossier.title,
                        topic=comparison.topic,
                        observation=row,
                        source=source,
                        intermediary=intermediary,
                    )
                    matches.append((score, match))
    return [match for _, match in sorted(matches, key=lambda item: -item[0])[:10]]
