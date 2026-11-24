# ADR 0002 — Catalog and HTTP API versions

Status: Accepted.

The original catalog was a single JSON document with `schema_version: 1`. Version 2 uses evidence links with explicit roles and a declared source-provenance graph. See [the catalog guide](../../data/catalog/README.md) for validation and migration rules.

The operational endpoint `/health` sits outside the versioned API. The public contract begins at `/api/v1`. The package version and catalog schema revision serve separate purposes.
