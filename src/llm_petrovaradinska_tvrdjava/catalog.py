import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from .models import Catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a source and claim catalog.")
    parser.add_argument("catalog", type=Path, nargs="?", default=Path("data/catalog/catalog.json"))
    args = parser.parse_args(argv)

    try:
        catalog = Catalog.model_validate_json(args.catalog.read_bytes())
    except (OSError, ValidationError) as exc:
        print(f"{args.catalog}: {exc}", file=sys.stderr)
        return 1

    print(f"{args.catalog}: valid ({len(catalog.sources)} sources, {len(catalog.claims)} claims)")
    return 0
