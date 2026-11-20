import argparse
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import ValidationError

from llm_petrovaradinska_tvrdjava.reviews import Dossier, SourceReview

DEFAULT_DOSSIER = Path("src/llm_petrovaradinska_tvrdjava/review_data/petrovaradin-1716.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record an editorial review of a source report.")
    parser.add_argument("observation_id")
    parser.add_argument("--file", type=Path, default=DEFAULT_DOSSIER)
    parser.add_argument("--verdict", choices=["verified", "needs_context"], required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--note", required=True)
    args = parser.parse_args(argv)

    try:
        dossier = Dossier.model_validate_json(args.file.read_bytes())
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

    observation = next(
        (
            row
            for comparison in dossier.comparisons
            for row in comparison.observations
            if row.observation_id == args.observation_id
        ),
        None,
    )
    if observation is None:
        parser.error(f"Unknown observation: {args.observation_id}")

    observation.review = review
    temporary = None
    try:
        with NamedTemporaryFile(dir=args.file.parent, delete=False) as stream:
            temporary = Path(stream.name)
            contents = dossier.model_dump_json(indent=2, exclude_none=True) + "\n"
            stream.write(contents.encode("utf-8"))
        temporary.replace(args.file)
    except OSError as error:
        parser.error(str(error))
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)

    print(f"{observation.observation_id}: {review.verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
