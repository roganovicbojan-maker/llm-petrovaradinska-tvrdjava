from html import escape
from importlib.resources import files
from string import Template

from .reviews import Citation, Dossier, DossierSource, Observation, ReviewMatch

KIND_LABEL = {"primary": "Primarni izvor", "secondary": "Sekundarni izvor", "map": "Karta"}
VERDICT_LABEL = {"verified": "Proveren navod", "needs_context": "Potreban kontekst"}


def render_citation(citation: Citation, source: DossierSource) -> str:
    title = escape(source.title)
    locator = escape(citation.locator)
    if source.url:
        title = f'<a href="{escape(str(source.url))}">{title}</a>'
    return f"{title}<small>{locator}</small>"


def render_observation(row: Observation, sources: dict[str, DossierSource]) -> str:
    source = sources[row.citation.source_id]
    citation = render_citation(row.citation, source)
    if row.via:
        intermediary = render_citation(row.via, sources[row.via.source_id])
        citation += f'<div class="via">Prema posredniku<br>{intermediary}</div>'

    review = row.review
    label = VERDICT_LABEL[review.verdict] if review else "Čeka proveru"
    status = f'<span class="status">{label}</span>'
    if review:
        status += (
            f"<small>{escape(review.reviewer)} · {review.checked_on.isoformat()}</small>"
            f"<small>{escape(review.note)}</small>"
        )
    return (
        f'<tr id="{escape(row.observation_id)}"><th scope="row">'
        f"{escape(source.tradition)}<small>{KIND_LABEL[source.kind]}</small></th>"
        f"<td><strong>{escape(row.value)}</strong><small>{escape(row.context)}</small></td>"
        f"<td>{citation}</td><td>{status}</td></tr>"
    )


def render_dossier(dossier: Dossier) -> str:
    sources = {source.source_id: source for source in dossier.sources}
    sections = []
    for comparison in dossier.comparisons:
        rows = "".join(render_observation(row, sources) for row in comparison.observations)
        title = escape(comparison.topic)
        sections.append(
            f'<section><h2>{title}</h2><div class="scroll"><table aria-label="{title}">'
            "<thead><tr><th scope='col'>Perspektiva</th><th scope='col'>Navod</th>"
            "<th scope='col'>Izvor i lokator</th><th scope='col'>Urednička provera</th>"
            f"</tr></thead><tbody>{rows}</tbody></table></div></section>"
        )
    dossier_id = escape(dossier.dossier_id)
    navigation = (
        '<a href="/reviews">Svi dosijei</a> '
        f'<a href="/api/v1/reviews/{dossier_id}">JSON dosijea</a>'
    )
    return render_review_template(dossier.title, dossier.summary, "".join(sections), navigation)


def render_review_index(dossiers: list[Dossier], query: str, matches: list[ReviewMatch]) -> str:
    field = (
        '<form action="/reviews" method="get"><label for="query">Pretraži navode</label><br>'
        f'<input id="query" name="q" maxlength="160" value="{escape(query)}" '
        'placeholder="Na primer: Beogradska kapija"><button>Pretraži</button></form>'
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
            f"<h2>Pronađeni navodi</h2><ol>{''.join(hits)}</ol>"
            if hits
            else ("<p>U dostupnim dosijeima nema odgovarajućih navoda.</p>")
        )
        field += f"<section>{result}</section>"
    answer_form = (
        files(__package__).joinpath("review_data", "answer.html").read_text(encoding="utf-8")
    )
    return render_review_template(
        "Istraživački dosijei", "", answer_form + field + dossier_links, ""
    )


def render_review_template(title: str, summary: str, sections: str, navigation: str) -> str:
    template = files(__package__).joinpath("review_data", "review.html").read_text(encoding="utf-8")
    return Template(template).substitute(
        title=escape(title),
        summary=f"<p>{escape(summary)}</p>" if summary else "",
        sections=sections,
        navigation=navigation,
    )
