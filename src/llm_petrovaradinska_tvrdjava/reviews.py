import re
import unicodedata
from importlib.resources import files
from typing import Annotated, Literal, Self

from pydantic import Field, HttpUrl, model_validator

from .models import RECORD_ID_PATTERN, Record, RecordId, Review, Text

ReviewVerdict = Literal["verified", "needs_context"]


class SourceReview(Review):
    verdict: ReviewVerdict
    note: Text


class DossierSource(Record):
    source_id: RecordId
    title: Text
    tradition: Text
    kind: Literal["primary", "secondary", "map"]
    url: HttpUrl | None = None


class Citation(Record):
    source_id: RecordId
    locator: Text


class Observation(Record):
    observation_id: RecordId
    citation: Citation
    via: Citation | None = None
    value: Text
    context: Text
    review: SourceReview | None = None


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
    resource = files(__package__).joinpath("review_data", f"{dossier_id}.json")
    dossier = Dossier.model_validate_json(resource.read_bytes())
    if dossier.dossier_id != dossier_id:
        raise ValueError(f"Dossier ID does not match filename: {dossier_id}")
    return dossier


def load_demo_dossier() -> Dossier:
    return load_dossier("petrovaradin-1716")


def load_dossiers() -> list[Dossier]:
    directory = files(__package__).joinpath("review_data")
    return [
        load_dossier(resource.name.removesuffix(".json"))
        for resource in sorted(directory.iterdir(), key=lambda entry: entry.name)
        if resource.is_file() and resource.name.endswith(".json")
    ]


class ReviewMatch(Record):
    dossier_id: RecordId
    dossier_title: Text
    topic: Text
    observation: Observation
    source: DossierSource
    intermediary: DossierSource | None = None


TOKEN_PATTERN = re.compile(r"[^\W_]+")
QUESTION_WORDS = {"je", "za", "sto", "sta", "su", "na", "iz", "od", "ko", "kod", "koje", "kako"}


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
    return {word for word in TOKEN_PATTERN.findall(normalized) if len(word) > 1} - QUESTION_WORDS


def search_dossiers(dossiers: list[Dossier], query: str) -> list[ReviewMatch]:
    terms = search_terms(query)
    if not terms:
        return []

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
