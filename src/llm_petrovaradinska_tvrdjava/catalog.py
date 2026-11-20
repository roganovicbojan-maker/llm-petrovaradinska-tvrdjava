import argparse
import json
import sys
from importlib.resources import files
from pathlib import Path

from pydantic import ValidationError

from .models import Catalog


def load_catalog(path: Path | None = None) -> Catalog:
    resource = (
        path if path is not None else files(__package__).joinpath("review_data", "catalog.json")
    )
    return Catalog.model_validate_json(resource.read_bytes())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a source and claim catalog.")
    parser.add_argument("catalog", type=Path, nargs="?")
    parser.add_argument(
        "--json-schema", action="store_true", help="Print the current catalog JSON Schema and exit."
    )
    args = parser.parse_args(argv)
    if args.json_schema:
        print(json.dumps(Catalog.model_json_schema(), ensure_ascii=True, indent=2))
        return 0

    label = args.catalog or "Bundled catalog"
    try:
        catalog = load_catalog(args.catalog)
    except (OSError, ValidationError) as exc:
        print(f"{label}: {exc}", file=sys.stderr)
        return 1

    print(f"{label}: valid ({len(catalog.sources)} sources, {len(catalog.claims)} claims)")
    return 0
