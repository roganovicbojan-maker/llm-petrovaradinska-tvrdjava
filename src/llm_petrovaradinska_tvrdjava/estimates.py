from .models import Citation, Estimate, Record
from .reviews import ReviewMatch


class ComparedEstimate(Record):
    observation_id: str
    citation: Citation
    source_title: str
    estimate: Estimate


class EstimateComparison(Record):
    dossier_id: str
    topic: str
    estimates: list[ComparedEstimate]


def compare_estimates(
    matches: list[ReviewMatch], cited: list[ReviewMatch]
) -> list[EstimateComparison]:
    topics = {
        (match.dossier_id, match.topic) for match in cited if match.observation.estimate is not None
    }
    groups: dict[tuple[str, str], dict[str, ComparedEstimate]] = {}
    for match in matches:
        key = (match.dossier_id, match.topic)
        row = match.observation
        if key not in topics or row.estimate is None or row.status == "refuted":
            continue
        groups.setdefault(key, {})[row.observation_id] = ComparedEstimate(
            observation_id=row.observation_id,
            citation=row.citation,
            source_title=match.source.title,
            estimate=row.estimate,
        )

    comparisons = []
    for (dossier, topic), items in groups.items():
        estimates = list(items.values())
        sources = {item.citation.source_id for item in estimates}
        quantities = {
            (item.estimate.value, item.estimate.low, item.estimate.high) for item in estimates
        }
        if len(sources) > 1 and len(quantities) > 1:
            comparisons.append(
                EstimateComparison(dossier_id=dossier, topic=topic, estimates=estimates)
            )
    return comparisons
