# Source and claim catalog

The [bundled catalog](../../src/llm_petrovaradinska_tvrdjava/review_data/catalog.json) uses schema version 2. Pydantic models in `src/llm_petrovaradinska_tvrdjava/models.py` define the contract. To export the schema, run `python tools/validate_catalog.py --json-schema > catalog.schema.json` from the repository root using the project interpreter.

- List all known immediate ancestors in `derived_from`. Each source ID must exist. Cycles are rejected.
- A `confirmed` claim needs two supporting passages with disjoint sets of eligible root sources. The check uses recorded provenance. The editor checks its completeness and whether the passages support the claim.
- Evidence roles are `supports`, `contradicts`, and `context`. Supply `locator_unavailable_reason` for an unavailable locator. Passages for assessed claims must be checked against the original. Keep conflicting estimates separate and include units, counted populations, and counting definitions.
- Use registered BCP 47 language tags and ISO 15924 script codes. The validator allows up to 15 words per quotation from sources with unknown or restricted rights. The editor checks publication rights and total usage.
- Preserve the original date and calendar. Numeric bounds use the declared calendar. Normalized Gregorian values use `YYYY`, `YYYY-MM`, or `YYYY-MM-DD` with the corresponding precision. Document the conversion method and convention. The validator checks format, date validity, and order, and compares directly comparable Gregorian values.
- Use `dating` for archaeological ages. Include the method, unit, and published uncertainty. `ka` means thousands of years and `cal_years_bp` means calibrated years before present. Distinguish the inference from dated sediment from direct dating of an artefact.
- `Place` supports historical aliases, Wikidata IDs, and a coordinate pair.

## Migration from version 1

Convert the single `evidence` record into a list. Assign roles to records from `supporting_evidence` and `contradicting_evidence`, and select the role of the original passage according to its content. Record each passage once. For a date without a numeric bound, supply a supported normalization or preserve the original expression as part of an archaeological dating record. Set `schema_version` to `2` and run the validator.

## Dossiers

The catalog is the source of truth for claims and sources. Dossiers group `claim_ids` under titles and summaries. The public dossier shows all evidence. Its first evidence link also populates the legacy `citation` and `via` fields for API compatibility.

A `via` citation requires a `derived_from` path from the intermediary to the source and a locator in the intermediary edition. Check that the intermediary actually conveys the observation. Use `editorial_review` to record the editorial check of how the observation was reported. Use `review` and `status` for expert assessment. Migrated observations without documented assessment use `unknown`.
