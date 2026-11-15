"""Serve approved historical D7 aggregates and their declared assets."""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.road_safety_release import ReleaseUnavailable, approved_bytes, verify_release
from app.schemas.common import APIResponse
from app.services.overview_metadata import CAVEATS, RATIOS, TABLES, caveats, counts, state, units

router = APIRouter()
logger = logging.getLogger(__name__)
KIND = "descriptive_release"
VERSION = "v3-d7-2"
MANIFEST_SHA256 = "ec9def348fc67561f7ee2a5c7b3307a7db42b6e8832d7df7cc04252b87e70a82"
SCHEMA_VERSION = 1
APPROVED = "APPROVED_AGGREGATE_RELEASE"
ASSETS = {
    "county_boundary.geojson": "application/geo+json",
    "county_grid.svg": "image/svg+xml",
    "descriptive_release_data_dictionary.md": "text/markdown",
}
OUTPUTS = {*ASSETS, *(f"{table}.{extension}" for table in TABLES for extension in ("json", "csv"))}
UNAVAILABLE = {
    "code": "OVERVIEW_UNAVAILABLE",
    "message": "The reviewed Road Safety Overview dataset is unavailable.",
    "approval_state": None,
    "data": None,
}


def unavailable():
    return HTTPException(503, detail=UNAVAILABLE, headers={"Cache-Control": "no-store"})


@dataclass
class Release:
    path: Path
    manifest: dict

    def payload(self, name):
        try:
            if name not in OUTPUTS:
                raise ReleaseUnavailable("Unsupported D7 artifact")
            return approved_bytes(self.path, self.manifest, name)
        except ReleaseUnavailable as exc:
            logger.warning("D7 artifact unavailable: %s", exc)
            raise unavailable() from exc

    def bundle(self, name=None):
        return {
            "kind": KIND,
            "version": self.manifest["version"],
            "manifest_sha256": MANIFEST_SHA256,
            "output_sha256": self.manifest["outputs"].get(name),
            "approval_state": APPROVED,
        }

    def provenance(self, name=None):
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.manifest["run_id"],
            "sources": self.manifest["inputs"],
            "bundle": self.bundle(name),
        }

    def rows(self, table):
        try:
            return json.loads(self.payload(f"{table}.json"))
        except (UnicodeError, ValueError) as exc:
            logger.warning("Could not decode verified D7 table %s: %s", table, exc)
            raise unavailable() from exc

    def period(self, row):
        scope = self.manifest["scope"]
        start = row.get("period_start", scope["period_start"])
        end = row.get("period_end", scope["period_end"])
        return {
            "period_start": start,
            "period_end": end,
            "period_grain": row.get("period_grain", "year" if start == end else "period"),
        }

    def grid(self):
        # Mapping coverage uses all reports, including reports excluded from the map.
        full = next(row for row in self.rows("coordinate_coverage") if row["period_grain"] == "county")
        return {**self.manifest["grid"], "reported_crashes": full["reported_crashes"],
                "mapped_percent_of_reported": full["mapped_percent_of_reported"]}


def reviewed_release(response: Response):
    # Approval can be revoked by changing the external ledger. Recheck it on every read.
    root = Path(os.environ.get("ROAD_SAFETY_RELEASE_ROOT", "data/exports/road_safety"))
    approvals = os.environ.get("ROAD_SAFETY_APPROVALS")
    try:
        if not approvals:
            raise ReleaseUnavailable("Approval ledger is absent")
        path = root / KIND
        manifest = verify_release(path, approvals, KIND, expected_manifest_sha256=MANIFEST_SHA256)
        scope = manifest["scope"]
        if (
            manifest["version"] != VERSION or type(manifest["schema_version"]) is not int
            or manifest["schema_version"] != SCHEMA_VERSION or scope["geoid"] != "42003"
            or (scope["period_start"], scope["period_end"]) != (2004, 2024)
            or scope["claim_class"] != "HISTORICAL_DESCRIPTIVE_AGGREGATES"
            or scope["PRIMARY_SITE_ASSIGNMENTS_ACCEPTED"] != 0
            or not OUTPUTS <= manifest["outputs"].keys()
        ):
            raise ReleaseUnavailable("Unsupported D7 schema or scope")
    except (ReleaseUnavailable, KeyError) as exc:
        logger.info("Overview unavailable: %s", exc)
        raise unavailable() from exc
    response.headers["Cache-Control"] = "no-store"
    return Release(path, manifest)


def table_metadata(table, release):
    if table not in TABLES:
        raise unavailable()
    key, population = TABLES[table]
    return {
        "table_id": table,
        "row_key": key,
        **release.period({}),
        "geographic_grain": "occupied_clipped_grid_cell" if table == "historical_grid" else "county_extract",
        "geoid": release.manifest["scope"]["geoid"],
        "population": population,
        **({"grid": release.grid(), "caveat_codes": ["GRID_CONCENTRATION"]} if table == "historical_grid" else {}),
        **release.provenance(f"{table}.json"),
    }


@router.get("/provenance", response_model=APIResponse[dict])
def provenance(release: Release = Depends(reviewed_release)):
    manifest = release.manifest
    return APIResponse(data={
        **release.provenance(), "scope": manifest["scope"], "manifest_status": manifest["status"],
        "tables": manifest["tables"], "outputs": {name: manifest["outputs"][name] for name in sorted(OUTPUTS)},
        "grid": release.grid(),
    })


@router.get("/tables/{table_id}", response_model=APIResponse[dict])
def table_rows(table_id: str, release: Release = Depends(reviewed_release)):
    data = table_metadata(table_id, release)
    rows = release.rows(table_id)
    if rows and "period_start" in rows[0]:
        data.update(release.period({
            "period_start": min(row["period_start"] for row in rows),
            "period_end": max(row["period_end"] for row in rows),
        }))
    columns = {column: units(column, value) for column, value in (rows[0].items() if rows else ())}
    # Shared column metadata keeps the 38,332-cell response compact. Row annotations are sparse.
    annotations = {}
    for index, row in enumerate(rows):
        nulls = {column: state(column, row) for column, value in row.items() if value is None}
        codes = [] if table_id == "historical_grid" else caveats(table_id, row)
        if nulls or codes:
            annotations[index] = {"nulls": nulls, "caveat_codes": codes}
    return APIResponse(data={
        **data, "rows": rows, "units": columns, "annotations": annotations,
        "ratios": {column: RATIOS[column] for column in columns.keys() & RATIOS.keys()},
        "caveats": CAVEATS,
    })


@router.get("/tables/{table_id}/metrics/{column}", response_model=APIResponse[dict])
def metric(table_id: str, column: str, request: Request, release: Release = Depends(reviewed_release)):
    data = table_metadata(table_id, release)
    keys = data["row_key"]
    if sorted(key for key, _ in request.query_params.multi_items()) != sorted(keys):
        raise HTTPException(422, detail="Supply the table's complete row key.")
    row = next((row for row in release.rows(table_id)
                if all(str(row[key]) == request.query_params[key] for key in keys)), None)
    if row is None or column not in row:
        raise HTTPException(404, detail="Overview metric or row was not found.")
    numerator, denominator = counts(column, row)
    return APIResponse(data={
        **data, **release.period(row), "population": row.get("population", data["population"]),
        "row": row, "metric_id": f"{table_id}.{column}", "value": row[column], **state(column, row),
        "units": units(column, row[column]), "numerator": numerator, "denominator": denominator,
        "coverage": {key: value for key, value in row.items() if units(key, value) == "crashes"},
        "caveats": [{"code": code, "caption": CAVEATS[code]} for code in caveats(table_id, row)],
    })


def artifact(release, name, media_type, manifest_sha256):
    bundle = release.bundle(name)
    if manifest_sha256 is not None and manifest_sha256 != bundle["manifest_sha256"]:
        raise unavailable()
    payload = release.payload(name)
    return Response(payload, media_type=media_type, headers={
        "Cache-Control": "no-store",
        "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'",
        "X-Content-Type-Options": "nosniff",
        "X-Bundle-Version": bundle["version"], "X-Manifest-SHA256": bundle["manifest_sha256"],
        "X-Artifact-SHA256": bundle["output_sha256"],
        "Link": '<../provenance>; rel="describedby"',
    })


@router.get("/downloads/{table_id}")
def download(table_id: str, manifest_sha256: str | None = None, release: Release = Depends(reviewed_release)):
    if table_id not in TABLES:
        raise unavailable()
    response = artifact(release, f"{table_id}.csv", "text/csv", manifest_sha256)
    response.headers["Content-Disposition"] = f'attachment; filename="{table_id}.csv"'
    return response


@router.get("/assets/{name}")
def asset(name: str, manifest_sha256: str | None = None, release: Release = Depends(reviewed_release)):
    if name not in ASSETS:
        raise unavailable()
    return artifact(release, name, ASSETS[name], manifest_sha256)
