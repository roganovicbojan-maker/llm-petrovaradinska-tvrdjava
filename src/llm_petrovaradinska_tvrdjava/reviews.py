import re
import unicodedata
from collections import Counter
from collections.abc import Iterator
from difflib import get_close_matches
from math import log1p
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


def iter_review_matches(dossiers: list[Dossier]) -> Iterator[ReviewMatch]:
    for dossier in dossiers:
        sources = {source.source_id: source for source in dossier.sources}
        for comparison in dossier.comparisons:
            for row in comparison.observations:
                yield ReviewMatch(
                    dossier_id=dossier.dossier_id,
                    dossier_title=dossier.title,
                    topic=comparison.topic,
                    observation=row,
                    source=sources[row.citation.source_id],
                    intermediary=sources[row.via.source_id] if row.via else None,
                )


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
    "kao",
    "kada",
    "bilo",
    "bila",
    "imao",
    "se",
    "da",
    "on",
    "who",
    "how",
    "many",
    "the",
    "did",
    "was",
    "were",
    "of",
    "in",
    "at",
    "wie",
    "viele",
    "der",
    "die",
    "dem",
    "wurden",
    "bei",
    "im",
    "hany",
    "az",
    "volt",
    "es",
    "kac",
    "bir",
    "icin",
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
    "topovima": "topova",
    "top": "topova",
    "cannons": "topova",
    "cannon": "topova",
    "kanonen": "topova",
    "agyu": "topova",
    "agyut": "topova",
    "toplar": "topova",
    "captured": "zaplenjeni",
    "erbeutet": "zaplenjeni",
    "ele": "zaplenjeni",
    "gecirildi": "zaplenjeni",
    "zsakmanyoltak": "zaplenjeni",
    "zaplenjenih": "zaplenjeni",
    "zaplenjeno": "zaplenjeni",
    "zaplenjene": "zaplenjeni",
    "prijavio": "izvestava",
    "eugena": "eugen",
    "karagoza": "karagoz",
    "bici": "bitka",
    "bitke": "bitka",
    "procena": "procene",
    "ottoman": "osmanlije",
    "ottomans": "osmanlije",
    "osmanlija": "osmanlije",
    "osmanski": "osmanlije",
    "osmanske": "osmanlije",
    "osmanskom": "osmanlije",
    "komandovao": "zapovednici",
    "osmanli": "osmanlije",
    "turcima": "osmanlije",
    "turci": "osmanlije",
    "losses": "gubici",
    "casualties": "gubici",
    "verluste": "gubici",
    "vesztesegek": "gubici",
    "kayiplari": "gubici",
    "siege": "opsada",
    "belagerung": "opsada",
    "ostroma": "opsada",
    "kusatmasi": "opsada",
}
QUERY_CONTEXT = {
    "petrovaradin",
    "petrovaradina",
    "petrovaradinu",
    "tvrdjava",
    "tvrdjave",
    "tvrdjavi",
    "fortress",
    "festung",
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


def normalized_tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize(
        "NFKD", text.casefold().translate(SERBIAN_CYRILLIC).replace("đ", "dj")
    )
    normalized = "".join(letter for letter in normalized if not unicodedata.combining(letter))
    return TOKEN_PATTERN.findall(normalized)


def search_terms(
    text: str, places: dict[str, str] | None = None, *, fuzzy: bool = False
) -> set[str]:
    places = places or {}
    text = " ".join(normalized_tokens(text))
    for alias, canonical in sorted(places.items(), key=lambda item: -len(item[0])):
        if " " in alias:
            text = re.sub(rf"\b{re.escape(alias)}\b", canonical.replace(" ", "_"), text)
    terms = set()
    for word in text.split():
        if len(word) <= 1 or word in QUESTION_WORDS:
            continue
        normalized = places.get(word, SEARCH_ALIASES.get(word, word)).replace(" ", "_")
        if fuzzy and normalized == word and len(word) >= 8:
            options = get_close_matches(word, places, n=1, cutoff=0.92)
            if options:
                normalized = places[options[0]].replace(" ", "_")
        terms.add(normalized)
    return terms


def search_dossiers(dossiers: list[Dossier], query: str) -> list[ReviewMatch]:
    places = {"petrovaradin": "petrovaradin"}
    for dossier in dossiers:
        for comparison in dossier.comparisons:
            for row in comparison.observations:
                if row.location is None:
                    continue
                if "petrovaradin" not in normalized_tokens(row.location.modern_name):
                    continue
                names = [row.location.original_name, *row.location.aliases]
                for name in names:
                    if name is not None:
                        alias = " ".join(normalized_tokens(name))
                        if alias:
                            places[alias] = "petrovaradin"
    terms = search_terms(query, places, fuzzy=True)
    if not terms:
        return []

    topical_terms = {term for term in terms - QUERY_CONTEXT if not term.isdecimal()}
    rows = []
    frequency: Counter[str] = Counter()
    for match in iter_review_matches(dossiers):
        row = match.observation
        source = match.source
        dossier_terms = search_terms(match.dossier_title, places)
        topic_terms = search_terms(match.topic, places)
        value_terms = search_terms(row.value, places)
        evidence_terms = search_terms(
            f"{row.context} {row.citation.locator} {source.title} {source.tradition}", places
        )
        if source.kind == "map":
            evidence_terms.add("karta")
        for evidence in row.evidence:
            evidence_terms |= search_terms(
                f"{evidence.passage} {evidence.locator} {evidence.source.title}", places
            )
        document_terms = value_terms | topic_terms | evidence_terms | dossier_terms
        frequency.update(document_terms)
        rows.append(
            (match, value_terms, topic_terms | evidence_terms, dossier_terms, document_terms)
        )
    if not rows:
        return []
    average_length = sum(len(row[-1]) for row in rows) / len(rows)
    matches = []
    for match, values, context_terms, title, document in rows:
        covered_topics = topical_terms & document
        if topical_terms and len(covered_topics) <= len(topical_terms) // 2:
            continue
        score = 0.0
        normalization = 1.2 * (0.25 + 0.75 * len(document) / average_length)
        for term in terms & document:
            tf = 4 * (term in values) + 2 * (term in context_terms) + (term in title)
            idf = log1p((len(rows) - frequency[term] + 0.5) / (frequency[term] + 0.5))
            score += idf * tf * 2.2 / (tf + normalization)
        if score:
            matches.append((score, match))
    return [match for _, match in sorted(matches, key=lambda item: -item[0])[:10]]
