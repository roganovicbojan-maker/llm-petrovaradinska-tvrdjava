from html import escape
from importlib.resources import files
from string import Template

from .models import Citation
from .reviews import Dossier, DossierSource, Observation, ReviewMatch

KIND_LABEL = {"primary": "Primary source", "secondary": "Secondary source", "map": "Map"}
VERDICT_LABEL = {"verified": "Reviewed observation", "needs_context": "Context needed"}
STATUS_LABEL = {
    "confirmed": "Confirmed",
    "probable": "Probable",
    "disputed": "Disputed",
    "refuted": "Refuted",
    "unknown": "Unknown",
}
CONFIDENCE_LABEL = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "unassessed": "unassessed",
}
ROLE_LABEL = {"supports": "Supports", "contradicts": "Contradicts", "context": "Context"}


def render_citation(citation: Citation, source: DossierSource) -> str:
    title = escape(source.title)
    locator = escape(citation.locator)
    if source.url:
        title = f'<a href="{escape(str(source.url))}">{title}</a>'
    edition = (
        f"<small>{escape(source.edition_or_translation)}</small>"
        if (source.edition_or_translation)
        else ""
    )
    bibliography = (
        f"<small>{escape(source.bibliography)}</small>"
        if (source.bibliography and source.bibliography != source.title)
        else ""
    )
    year = (
        f"<small>Publication year {source.publication_year}</small>"
        if (source.publication_year is not None)
        else ""
    )
    return f"{title}{edition}{year}{bibliography}<small>{locator}</small>"


def render_observation(row: Observation, sources: dict[str, DossierSource]) -> str:
    source = sources[row.citation.source_id]
    items = []
    for evidence in row.evidence:
        citation = render_citation(
            Citation(source_id=evidence.source_id, locator=evidence.locator), evidence.source
        )
        if evidence.via and evidence.intermediary:
            intermediary = render_citation(evidence.via, evidence.intermediary)
            citation += f'<div class="via">Via intermediary<br>{intermediary}</div>'
        reason = evidence.locator_unavailable_reason
        item = f"<strong>{ROLE_LABEL[evidence.role]}</strong><br>{citation}"
        if reason:
            item += f"<small>Locator unavailable. {escape(reason)}</small>"
        item += f"<small>{escape(evidence.passage)}</small>"
        items.append(f"<li>{item}</li>")
    evidence_html = f"<ul>{''.join(items)}</ul>"

    review = row.review
    label = VERDICT_LABEL[review.verdict] if review else "Awaiting review"
    status = (
        f'<span class="status">{STATUS_LABEL[row.status]}</span>'
        f"<small>Confidence: {CONFIDENCE_LABEL[row.confidence]}</small>"
    )
    if row.expert_review:
        expert = row.expert_review
        status += (
            f"<small>Expert review: {escape(expert.reviewer)} "
            f"({expert.checked_on.isoformat()})</small>"
        )
    status += f"<small>Editorial source review: {label}</small>"
    if review:
        status += (
            f"<small>{escape(review.reviewer)} · {review.checked_on.isoformat()}</small>"
            f"<small>{escape(review.note)}</small>"
        )
    details = ""
    if row.disagreement_notes:
        details += f"<small>Disagreement: {escape(row.disagreement_notes)}</small>"
    if row.estimate:
        estimate = row.estimate
        bounds = f"{estimate.low}–{estimate.high}" if estimate.low is not None else ""
        value = str(estimate.value) if estimate.value is not None else bounds
        if estimate.value is not None and bounds:
            value += f" ({bounds})"
        qualifier = "about " if estimate.approximate else ""
        details += (
            f"<small>Estimate: {qualifier}{value} {escape(estimate.unit)}. "
            f"{escape(estimate.counted_population)}. "
            f"{escape(estimate.counting_definition)}</small>"
        )
    return (
        f'<tr id="{escape(row.observation_id)}"><th scope="row">'
        f"{escape(source.tradition)}<small>{KIND_LABEL[source.kind]}</small></th>"
        f"<td><strong>{escape(row.value)}</strong>{details}</td>"
        f"<td>{evidence_html}</td><td>{status}</td></tr>"
    )


def render_dossier(dossier: Dossier) -> str:
    sources = {source.source_id: source for source in dossier.sources}
    sections = []
    for comparison in dossier.comparisons:
        rows = "".join(render_observation(row, sources) for row in comparison.observations)
        title = escape(comparison.topic)
        sections.append(
            f'<section><h2>{title}</h2><div class="scroll"><table aria-label="{title}">'
            "<thead><tr><th scope='col'>Perspective</th><th scope='col'>Observation</th>"
            "<th scope='col'>Source and locator</th><th scope='col'>Editorial review</th>"
            f"</tr></thead><tbody>{rows}</tbody></table></div></section>"
        )
    dossier_id = escape(dossier.dossier_id)
    navigation = (
        '<a href="/reviews">All dossiers</a> '
        f'<a href="/api/v1/reviews/{dossier_id}">Dossier JSON</a>'
    )
    return render_review_template(dossier.title, dossier.summary, "".join(sections), navigation)


def render_review_index(dossiers: list[Dossier], query: str, matches: list[ReviewMatch]) -> str:
    field = (
        '<form action="/reviews" method="get"><label for="query">Search observations</label><br>'
        f'<input id="query" name="q" maxlength="160" value="{escape(query)}" '
        'placeholder="Example: cannons captured in 1716"><button>Search</button></form>'
    )
    dossier_links = "".join(
        f'<section><h2><a href="/reviews/{escape(dossier.dossier_id)}">'
        f"{escape(dossier.title)}</a></h2><p>{escape(dossier.summary)}</p></section>"
        for dossier in dossiers
    )
    if query:
        hits = []
        for match in matches:
            row = match.observation
            href = f"/reviews/{escape(match.dossier_id)}#{escape(row.observation_id)}"
            hits.append(
                f'<li><a href="{href}">{escape(row.value)}</a>'
                f"<small>{escape(match.dossier_title)} · "
                f"{escape(row.citation.locator)}</small></li>"
            )
        result = (
            f"<h2>Matching observations</h2><ol>{''.join(hits)}</ol>"
            if hits
            else ("<p>No matching observations in the available dossiers.</p>")
        )
        field += f"<section>{result}</section>"
    answer_form = (
        files(__package__).joinpath("review_data", "answer.html").read_text(encoding="utf-8")
    )
    return render_review_template("Research dossiers", "", answer_form + field + dossier_links, "")


def render_review_template(title: str, summary: str, sections: str, navigation: str) -> str:
    template = files(__package__).joinpath("review_data", "review.html").read_text(encoding="utf-8")
    return Template(template).substitute(
        title=escape(title),
        summary=f"<p>{escape(summary)}</p>" if summary else "",
        sections=sections,
        navigation=navigation,
    )
