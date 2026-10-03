#!/usr/bin/env python3
"""Validate a BFDM Drive/Project ingestion checkout.

Run from repository root after an ingestion pass.
Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

BCS_RE = re.compile(r"^BCS-\d{6}$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{64}$")

REQUIRED_DB_TABLES = {
    "ingest_runs",
    "source_containers",
    "source_locators",
    "source_representations",
    "document_versions",
    "comments",
    "assets",
    "source_links",
    "ingest_warnings",
    "source_fts",
    "revision_fts",
    "comments_fts",
}

REQUIRED_METADATA_KEYS = {
    "schema_version",
    "corpus_id",
    "project",
    "project_slug",
    "title",
    "source_role",
    "source_kind",
    "authorship",
    "locators",
    "representations",
    "normalization",
    "capture_status",
    "ingested_at",
}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def load_json(path: Path, errors: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(errors, f"{path}: invalid JSON: {exc}")
        return None


def validate_jsonl(path: Path, id_key: str, errors: list[str]) -> list[dict]:
    rows = []
    ids = set()
    if not path.exists():
        fail(errors, f"missing required registry: {path}")
        return rows
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except Exception as exc:
            fail(errors, f"{path}:{n}: invalid JSON: {exc}")
            continue
        rid = row.get(id_key)
        if not rid:
            fail(errors, f"{path}:{n}: missing {id_key}")
        elif rid in ids:
            fail(errors, f"{path}:{n}: duplicate {id_key} {rid}")
        else:
            ids.add(rid)
        rows.append(row)
    return rows


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_metadata(repo: Path, errors: list[str], warnings: list[str]) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for base in (repo / "sources", repo / "context"):
        if not base.exists():
            continue
        for meta_path in base.glob("**/metadata.json"):
            meta = load_json(meta_path, errors)
            if not isinstance(meta, dict):
                continue
            missing = sorted(REQUIRED_METADATA_KEYS - set(meta))
            if missing:
                fail(errors, f"{meta_path}: missing keys {missing}")
            cid = meta.get("corpus_id")
            if not isinstance(cid, str) or not BCS_RE.match(cid):
                fail(errors, f"{meta_path}: invalid corpus_id {cid!r}")
                continue
            if cid in records:
                fail(errors, f"duplicate metadata container {cid}: {meta_path}")
            records[cid] = meta

            reps = meta.get("representations", [])
            if not isinstance(reps, list):
                fail(errors, f"{meta_path}: representations is not a list")
                continue
            for rep in reps:
                if not isinstance(rep, dict):
                    fail(errors, f"{meta_path}: invalid representation entry")
                    continue
                rpath = rep.get("path")
                expected = rep.get("sha256")
                if not rpath or not expected or not SHA_RE.match(str(expected)):
                    fail(errors, f"{meta_path}: representation missing valid path/sha256: {rep}")
                    continue
                file_path = repo / rpath
                if not file_path.exists():
                    fail(errors, f"{meta_path}: missing representation file {rpath}")
                    continue
                actual = sha256_file(file_path)
                if actual.lower() != str(expected).lower():
                    fail(errors, f"{meta_path}: SHA mismatch {rpath}: {actual} != {expected}")

            for field in ("locators",):
                if not isinstance(meta.get(field), list) or not meta[field]:
                    fail(errors, f"{meta_path}: {field} must be a non-empty list")

    if not records:
        warnings.append("no metadata.json source containers found; validator may be running before ingestion")
    return records


def validate_sqlite(repo: Path, errors: list[str], warnings: list[str]) -> set[str]:
    db = repo / "indexes" / "documents.sqlite"
    if not db.exists():
        warnings.append("indexes/documents.sqlite not found; no document database to validate")
        return set()

    conn = sqlite3.connect(str(db))
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchall()
        if integrity != [("ok",)]:
            fail(errors, f"SQLite integrity_check failed: {integrity}")

        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk:
            fail(errors, f"SQLite foreign_key_check returned {len(fk)} violations: {fk[:10]}")

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
            )
        }
        missing = sorted(REQUIRED_DB_TABLES - tables)
        if missing:
            fail(errors, f"SQLite missing required tables: {missing}")

        dup_native = conn.execute(
            """
            SELECT provider, native_id, COUNT(*), GROUP_CONCAT(DISTINCT corpus_id)
            FROM source_locators
            WHERE native_id IS NOT NULL
            GROUP BY provider, native_id
            HAVING COUNT(DISTINCT corpus_id) > 1
            """
        ).fetchall()
        if dup_native:
            fail(errors, f"native provider IDs map to multiple BCS records: {dup_native[:20]}")

        db_bcs = {row[0] for row in conn.execute("SELECT corpus_id FROM source_containers")}
        return db_bcs
    finally:
        conn.close()


def validate_temp_files(repo: Path, errors: list[str]) -> None:
    bad_suffixes = (".sqlite-wal", ".sqlite-shm", ".db-wal", ".db-shm", ".journal")
    bad_names = []
    for path in repo.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        s = str(path).lower()
        if s.endswith(bad_suffixes):
            bad_names.append(str(path.relative_to(repo)))
    if bad_names:
        fail(errors, f"temporary database files present: {bad_names}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".", help="repository root")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    errors: list[str] = []
    warnings: list[str] = []

    catalog = validate_jsonl(repo / "evidence" / "catalog.jsonl", "corpus_id", errors)
    validate_jsonl(repo / "evidence" / "evidence.jsonl", "evidence_id", errors)
    validate_jsonl(repo / "evidence" / "relations.jsonl", "relation_id", errors)

    catalog_ids = {r.get("corpus_id") for r in catalog if r.get("corpus_id")}
    metadata = validate_metadata(repo, errors, warnings)
    db_bcs = validate_sqlite(repo, errors, warnings)
    validate_temp_files(repo, errors)

    for cid in metadata:
        if cid not in catalog_ids:
            fail(errors, f"{cid}: source container metadata exists but evidence/catalog.jsonl has no BCS record")

    for cid in db_bcs:
        if cid not in catalog_ids:
            fail(errors, f"{cid}: SQLite source_containers row has no evidence/catalog.jsonl BCS record")

    print(f"catalog BCS records: {len(catalog_ids)}")
    print(f"human-readable source containers validated: {len(metadata)}")
    print(f"SQLite BCS records: {len(db_bcs)}")

    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    if errors:
        print(f"FAILED: {len(errors)} validation error(s)", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("OK: BFDM ingestion validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
