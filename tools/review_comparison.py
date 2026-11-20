import argparse
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import ValidationError

from llm_petrovaradinska_tvrdjava.catalog import load_catalog
from llm_petrovaradinska_tvrdjava.models import SourceReview

DEFAULT_CATALOG = Path("src/llm_petrovaradinska_tvrdjava/review_data/catalog.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record an editorial review of a source report.")
    parser.add_argument("observation_id")
    parser.add_argument("--file", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--verdict", choices=["verified", "needs_context"], required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--note", required=True)
    args = parser.parse_args(argv)

    try:
        catalog = load_catalog(args.file)
        review = SourceReview.model_validate(
            {
                "reviewer": args.reviewer,
                "checked_on": args.date,
                "verdict": args.verdict,
                "note": args.note,
            }
        )
    except (OSError, ValidationError) as error:
        parser.error(str(error))

    claim = next((item for item in catalog.claims if item.claim_id == args.observation_id), None)
    if claim is None:
        parser.error(f"Unknown observation: {args.observation_id}")

    claim.editorial_review = review
    temporary = None
    try:
        with NamedTemporaryFile(dir=args.file.parent, delete=False) as stream:
            temporary = Path(stream.name)
            contents = catalog.model_dump_json(indent=2, exclude_none=True) + "\n"
            stream.write(contents.encode("utf-8"))
        temporary.replace(args.file)
    except OSError as error:
        parser.error(str(error))
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)

    print(f"{claim.claim_id}: {review.verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
