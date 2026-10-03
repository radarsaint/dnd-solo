#!/usr/bin/env python3
"""Validate BFDM machine-readable project, series, server, and identity registries."""

from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"


def load_jsonl(name: str, id_key: str, errors: list[str]) -> list[dict]:
    path = REG / name
    if not path.exists():
        errors.append(f"missing {path}")
        return []
    rows = []
    seen = set()
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except Exception as exc:
            errors.append(f"{path}:{n}: invalid JSON: {exc}")
            continue
        rid = row.get(id_key)
        if not rid:
            errors.append(f"{path}:{n}: missing {id_key}")
        elif rid in seen:
            errors.append(f"{path}:{n}: duplicate {id_key} {rid}")
        else:
            seen.add(rid)
        rows.append(row)
    return rows


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    projects = load_jsonl("projects.jsonl", "project_id", errors)
    series = load_jsonl("series.jsonl", "series_id", errors)
    relations = load_jsonl("project_relations.jsonl", "relation_id", errors)
    people = load_jsonl("people.jsonl", "person_id", errors)
    identities = load_jsonl("identities.jsonl", "identity_id", errors)
    servers = load_jsonl("discord_servers.jsonl", "server_id", errors)

    project_ids = {r["project_id"] for r in projects if r.get("project_id")}
    series_ids = {r["series_id"] for r in series if r.get("series_id")}
    person_ids = {r["person_id"] for r in people if r.get("person_id")}
    server_ids = {r["server_id"] for r in servers if r.get("server_id")}
    identity_ids = {r["identity_id"] for r in identities if r.get("identity_id")}
    server_by_id = {r["server_id"]: r for r in servers if r.get("server_id")}
    identity_by_id = {r["identity_id"]: r for r in identities if r.get("identity_id")}

    # Source-container anchors should resolve against current evidence catalog.
    catalog_path = ROOT / "evidence" / "catalog.jsonl"
    bcs_ids = set()
    if catalog_path.exists():
        for n, raw in enumerate(catalog_path.read_text(encoding="utf-8").splitlines(), 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
                cid = row.get("corpus_id")
                if cid:
                    bcs_ids.add(cid)
            except Exception as exc:
                errors.append(f"{catalog_path}:{n}: invalid JSON: {exc}")
    else:
        warnings.append("evidence/catalog.jsonl missing; BCS anchor resolution skipped")

    order_seen = {}
    for p in projects:
        pid = p.get("project_id")
        for field in ("canonical_name", "aliases", "ordering", "primary_discord_servers", "staff"):
            if field not in p:
                errors.append(f"{pid}: missing Point 3 field {field}")
        sid_series = p.get("series_id")
        if sid_series is not None and sid_series not in series_ids:
            errors.append(f"{pid}: series_id {sid_series} not found")
        order = (p.get("ordering") or {}).get("development_index")
        if isinstance(order, int):
            if order in order_seen:
                errors.append(f"{pid}: duplicate development_index {order}")
            order_seen[order] = pid
        for sid in p.get("discord_servers", []):
            if sid not in server_ids:
                errors.append(f"{pid}: discord server ref {sid} not found in registry/discord_servers.jsonl")
        for anchor in p.get("source_anchors", []):
            if anchor.get("kind") == "BCS":
                cid = anchor.get("id")
                if cid not in bcs_ids:
                    errors.append(f"{pid}: BCS anchor {cid} not found in evidence/catalog.jsonl")

        live = (p.get("dates") or {}).get("live_window")
        if live is not None:
            if not live.get("start"):
                errors.append(f"{pid}: live_window exists without start")
            if not live.get("basis"):
                errors.append(f"{pid}: live_window exists without basis")
            if not live.get("source_refs"):
                errors.append(f"{pid}: live_window exists without source_refs")

        # Guard against pretending retrospective Roanoke range is a season count.
        scale = p.get("scale") or {}
        if scale.get("exact_concurrent_players") in ("30-100", "30–100"):
            errors.append(f"{pid}: 30–100 retrospective Roanoke range cannot be stored as an exact project count")
        rng = (scale.get("approximate_concurrency") or {}).get("range")
        if isinstance(rng, dict) and rng.get("min") == 30 and rng.get("max") == 100:
            errors.append(f"{pid}: 30–100 retrospective Roanoke range must remain series-level")
        for ctx in scale.get("series_context_refs", []):
            if ctx not in series_ids:
                errors.append(f"{pid}: scale series context {ctx} not found")
        for link in p.get("primary_discord_servers", []):
            server = server_by_id.get(link.get("server_id"))
            if not server:
                errors.append(f"{pid}: primary Discord server missing")
            else:
                if pid not in server.get("project_ids", []):
                    errors.append(f"{pid}: server {server.get('server_id')} does not link back")
                if link.get("slug") != server.get("server_slug"):
                    errors.append(f"{pid}: server slug mismatch")
        for staff in p.get("staff", []):
            if staff.get("person_id") not in person_ids:
                errors.append(f"{pid}: staff person {staff.get('person_id')} not found")

    for srec in series:
        sid = srec.get("series_id")
        for pid in srec.get("project_ids", []):
            if pid not in project_ids:
                errors.append(f"{sid}: project ref {pid} not found")
            else:
                project = next(p for p in projects if p.get("project_id") == pid)
                if project.get("series_id") != sid:
                    errors.append(f"{sid}: project {pid} does not link back")

    for rel in relations:
        a = rel.get("from_project_id")
        b = rel.get("to_project_id")
        if a not in project_ids:
            errors.append(f"{rel.get('relation_id')}: missing from_project_id {a}")
        if b not in project_ids:
            errors.append(f"{rel.get('relation_id')}: missing to_project_id {b}")
        if a == b:
            errors.append(f"{rel.get('relation_id')}: self-relation is not allowed")

    for s in servers:
        sid = s.get("server_id")
        for pid in s.get("project_ids", []):
            if pid not in project_ids:
                errors.append(f"server {sid}: project ref {pid} not found")
        stored = s.get("attachments_stored")
        expected = s.get("attachments_expected")
        if stored is not None and expected is not None and stored > expected:
            errors.append(f"server {sid}: attachments_stored > attachments_expected")
        resolution = s.get("brendon_identity_resolution") or {}
        status = resolution.get("status")
        iid = resolution.get("identity_id")
        if status == "RESOLVED":
            if not iid or iid not in identity_ids:
                errors.append(f"server {sid}: resolved Brendon identity missing or invalid")
            elif identity_by_id[iid].get("server_id") != sid:
                errors.append(f"server {sid}: resolved identity scope mismatch")
        elif status == "UNRESOLVED" and iid is not None:
            errors.append(f"server {sid}: unresolved identity must have null identity_id")

    for ident in identities:
        iid = ident.get("identity_id")
        pid = ident.get("person_id")
        if pid not in person_ids:
            errors.append(f"{iid}: person_id {pid} not found")
        if not ident.get("mapping_basis"):
            errors.append(f"{iid}: mapping_basis missing")
        if ident.get("server_id") and ident.get("server_id") not in server_ids:
            errors.append(f"{iid}: server_id does not resolve")
        if ident.get("project_id") and ident.get("project_id") not in project_ids:
            errors.append(f"{iid}: project_id does not resolve")
        if ident.get("platform") == "DISCORD" and "ATTRIBUTION_ALLOWED" in str(ident.get("attribution_use")):
            if not ident.get("account_id"):
                errors.append(f"{iid}: attribution-authorizing Discord identity lacks account_id")
            if not ident.get("server_id"):
                errors.append(f"{iid}: attribution-authorizing Discord identity lacks server_id")
        if ident.get("confidence") == "TENTATIVE" and "ATTRIBUTION_ALLOWED" in str(ident.get("attribution_use")):
            errors.append(f"{iid}: tentative identity cannot authorize attribution")

    print(f"projects: {len(projects)}")
    print(f"series: {len(series)}")
    print(f"project relations: {len(relations)}")
    print(f"people: {len(people)}")
    print(f"identity assertions: {len(identities)}")
    print(f"Discord servers: {len(servers)}")
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    if errors:
        print(f"FAILED: {len(errors)} registry error(s)", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("OK: BFDM registry validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
