#!/usr/bin/env python3
"""Reconcile the 51-source BFDM legacy staging bundle into canonical bfdm-corpus.

Conservative rules:
- existing BCS IDs are authoritative;
- archive records must agree with the preserved legacy manifest;
- existing target bytes are never overwritten;
- any differing target file is a hard conflict;
- source-container membership does not imply Brendon authorship.

Dry-run is the default. Use --apply only after reviewing the report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from collections import Counter
from pathlib import Path

BUNDLE_PREFIX = "brendon-corpus/"
REPO_MANIFEST = Path("research/legacy-staging/manifest.all.jsonl")
CATALOG = Path("evidence/catalog.jsonl")
DEFAULT_REPORT = Path("research/legacy-staging/reconciliation-report.json")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl_bytes(data: bytes) -> list[dict]:
    return [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]


def load_jsonl_path(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def index_by(rows: list[dict], key: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        value = row.get(key)
        if not value:
            raise ValueError(f"row missing {key}: {row}")
        if value in out:
            raise ValueError(f"duplicate {key}: {value}")
        out[value] = row
    return out


def normalize_manifest_record(row: dict) -> dict:
    keys = [
        "corpus_id",
        "project",
        "title",
        "original_filename",
        "original_sha256",
        "normalized_file",
        "normalized_sha256",
        "normalized_line_count",
        "assets",
        "comments_file",
        "warnings",
        "provenance_note",
        "brendon_native_comments_file",
        "original_stored_as",
        "_bundle_comments",
        "_bundle_path",
    ]
    return {k: row.get(k) for k in keys}


def parse_checksum_file(path: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            digest, rel = raw.split("  ", 1)
        except ValueError as exc:
            raise ValueError(f"{path}:{n}: malformed checksum line") from exc
        if rel in checksums:
            raise ValueError(f"{path}:{n}: duplicate checksum path {rel}")
        checksums[rel] = digest
    return checksums


def relevant_bundle_files(zf: zipfile.ZipFile, bundle_path: str) -> list[str]:
    prefix = BUNDLE_PREFIX + bundle_path.rstrip("/") + "/"
    return sorted(
        name for name in zf.namelist()
        if name.startswith(prefix) and not name.endswith("/")
    )


def rel_from_zip(name: str) -> str:
    if not name.startswith(BUNDLE_PREFIX):
        raise ValueError(f"unexpected zip path outside {BUNDLE_PREFIX}: {name}")
    return name[len(BUNDLE_PREFIX):]


def classify_file(
    zf: zipfile.ZipFile, zip_name: str, target: Path
) -> tuple[str, str, str | None]:
    archive_bytes = zf.read(zip_name)
    archive_sha = sha256_bytes(archive_bytes)
    if not target.exists():
        return "MISSING_TARGET", archive_sha, None
    target_sha = sha256_file(target)
    if target_sha == archive_sha:
        return "ALREADY_PRESENT", archive_sha, target_sha
    return "CONFLICT", archive_sha, target_sha


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--checksums", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    archive = args.archive.resolve()
    repo = args.repo_root.resolve()
    report_path = (args.report or (repo / DEFAULT_REPORT)).resolve()

    errors: list[str] = []
    warnings: list[str] = []
    archive_sha = sha256_file(archive)
    external_checksums = (
        parse_checksum_file(args.checksums.resolve()) if args.checksums else None
    )

    repo_manifest_path = repo / REPO_MANIFEST
    if not repo_manifest_path.exists():
        errors.append(f"missing canonical preserved manifest: {repo_manifest_path}")
        repo_manifest_rows: list[dict] = []
    else:
        repo_manifest_rows = load_jsonl_path(repo_manifest_path)

    catalog_path = repo / CATALOG
    if not catalog_path.exists():
        errors.append(f"missing evidence catalog: {catalog_path}")
        catalog_ids: set[str] = set()
    else:
        catalog_ids = {
            row.get("corpus_id")
            for row in load_jsonl_path(catalog_path)
            if row.get("corpus_id")
        }

    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        manifest_zip_name = BUNDLE_PREFIX + "manifest.all.jsonl"
        if manifest_zip_name not in names:
            errors.append(f"archive missing {manifest_zip_name}")
            archive_manifest_rows: list[dict] = []
        else:
            archive_manifest_rows = load_jsonl_bytes(zf.read(manifest_zip_name))

        try:
            archive_by_id = index_by(archive_manifest_rows, "corpus_id")
            repo_by_id = index_by(repo_manifest_rows, "corpus_id")
        except ValueError as exc:
            errors.append(str(exc))
            archive_by_id, repo_by_id = {}, {}

        archive_ids = set(archive_by_id)
        repo_ids = set(repo_by_id)
        if archive_ids != repo_ids:
            errors.append(
                "archive/repo legacy manifest ID mismatch: "
                f"only_archive={sorted(archive_ids-repo_ids)} "
                f"only_repo={sorted(repo_ids-archive_ids)}"
            )

        if len(archive_ids) != 51:
            errors.append(f"expected 51 legacy BCS IDs; found {len(archive_ids)}")

        for cid in sorted(archive_ids & repo_ids):
            if normalize_manifest_record(archive_by_id[cid]) != normalize_manifest_record(repo_by_id[cid]):
                errors.append(f"{cid}: preserved repo manifest differs semantically from archive manifest")
            if cid not in catalog_ids:
                errors.append(f"{cid}: absent from evidence/catalog.jsonl")

        for cid, row in sorted(archive_by_id.items()):
            bundle = row.get("_bundle_path")
            if not bundle:
                errors.append(f"{cid}: missing _bundle_path")
                continue
            for field, rel_field, sha_field in [
                ("original", row.get("original_stored_as"), "original_sha256"),
                ("normalized", row.get("normalized_file"), "normalized_sha256"),
            ]:
                if not rel_field:
                    errors.append(f"{cid}: missing {field} relative path")
                    continue
                zip_name = BUNDLE_PREFIX + bundle.rstrip("/") + "/" + rel_field
                if zip_name not in names:
                    errors.append(f"{cid}: archive missing {zip_name}")
                    continue
                actual = sha256_bytes(zf.read(zip_name))
                expected = row.get(sha_field)
                if actual != expected:
                    errors.append(
                        f"{cid}: {field} checksum mismatch "
                        f"expected={expected} actual={actual}"
                    )

        checksum_verified = 0
        if external_checksums is not None:
            for rel, expected in external_checksums.items():
                zip_name = BUNDLE_PREFIX + rel
                if zip_name not in names:
                    errors.append(f"checksum inventory names missing archive path: {rel}")
                    continue
                actual = sha256_bytes(zf.read(zip_name))
                if actual != expected:
                    errors.append(
                        f"checksum mismatch: {rel} expected={expected} actual={actual}"
                    )
                else:
                    checksum_verified += 1

        record_reports: list[dict] = []
        totals = Counter()
        project_records = Counter()
        project_assets = Counter()
        project_comments = Counter()

        for cid, row in sorted(archive_by_id.items()):
            bundle = row["_bundle_path"]
            files = relevant_bundle_files(zf, bundle)
            file_reports: list[dict] = []
            states = Counter()

            for zip_name in files:
                rel = rel_from_zip(zip_name)
                target = repo / rel
                state, archive_file_sha, target_sha = classify_file(
                    zf, zip_name, target
                )
                states[state] += 1
                totals[state] += 1
                file_reports.append(
                    {
                        "path": rel,
                        "status": state,
                        "archive_sha256": archive_file_sha,
                        "target_sha256": target_sha,
                        "size_bytes": zf.getinfo(zip_name).file_size,
                    }
                )

            if states["CONFLICT"]:
                record_status = "CONFLICT"
            elif states["MISSING_TARGET"] and states["ALREADY_PRESENT"]:
                record_status = "PARTIAL"
            elif states["MISSING_TARGET"]:
                record_status = "READY_TO_MIGRATE"
            else:
                record_status = "ALREADY_RECONCILED"

            project_records[row["project"]] += 1
            project_assets[row["project"]] += len(row.get("assets") or [])
            project_comments[row["project"]] += int(row.get("_bundle_comments") or 0)

            record_reports.append(
                {
                    "corpus_id": cid,
                    "project": row["project"],
                    "title": row["title"],
                    "bundle_path": bundle,
                    "status": record_status,
                    "files": file_reports,
                }
            )

        conflict_count = totals["CONFLICT"]
        preapply_errors = list(errors)

        applied = 0
        if args.apply and not errors and conflict_count == 0:
            for rec in record_reports:
                for file_record in rec["files"]:
                    if file_record["status"] != "MISSING_TARGET":
                        continue
                    zip_name = BUNDLE_PREFIX + file_record["path"]
                    target = repo / file_record["path"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(zip_name) as src, target.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
                    actual = sha256_file(target)
                    if actual != file_record["archive_sha256"]:
                        errors.append(
                            f"post-copy checksum mismatch: {file_record['path']}"
                        )
                        break
                    applied += 1
                if errors:
                    break
        elif args.apply and conflict_count:
            errors.append(
                f"refusing --apply because {conflict_count} "
                "conflicting target file(s) exist"
            )

    report = {
        "schema": "bfdm_legacy_reconciliation/v1",
        "archive": {
            "path": str(archive),
            "sha256": archive_sha,
            "legacy_records": len(archive_manifest_rows),
            "external_checksum_inventory": (
                str(args.checksums.resolve()) if args.checksums else None
            ),
            "external_checksums_verified": checksum_verified,
        },
        "repo_root": str(repo),
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "preapply_errors": preapply_errors,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "records": len(record_reports),
            "record_status_counts": dict(
                Counter(r["status"] for r in record_reports)
            ),
            "file_status_counts": dict(totals),
            "files_copied": applied,
            "projects": {
                project: {
                    "records": project_records[project],
                    "assets_declared": project_assets[project],
                    "bundle_comments_declared": project_comments[project],
                }
                for project in sorted(project_records)
            },
        },
        "records": record_reports,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "mode": report["mode"],
                "report": str(report_path),
                "archive_sha256": archive_sha,
                "records": report["summary"]["records"],
                "record_status_counts": report["summary"]["record_status_counts"],
                "file_status_counts": report["summary"]["file_status_counts"],
                "files_copied": applied,
                "errors": errors,
            },
            indent=2,
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
