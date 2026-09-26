#!/usr/bin/env python3
"""Build StreetLens' PCI road geometry at deploy/build time.

The dashboard's spreadsheet PCI data already lives in templates/index.html.
This script fetches the OSM road geometry once during the Vercel build, matches
it to those PCI names using the same normalization rules as the frontend, and
inlines the resulting GeoJSON into index.html. Runtime page loads therefore do
not wait for Overpass or /api/pci-roads.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "index.html"

OVERPASS_ENDPOINTS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# The original single bounding-box query was large enough to time out during
# some Vercel builds.  Split it into smaller tiles so each Overpass request is
# cheap and can succeed independently.
BOUNDS = (-75.091, 39.910, -75.062, 39.928)  # west, south, east, north
TILE_ROWS = 3
TILE_COLS = 3


def make_query(west: float, south: float, east: float, north: float) -> str:
    return (
        '[out:json][timeout:20];'
        f'way["highway"]["name"]({south},{west},{north},{east});'
        'out tags geom;'
    )



def normalize(value: str) -> str:
    value = str(value or "").lower()
    value = re.sub(r"[\[\]\(\),.\-–—]", " ", value)
    replacements = {
        "avenue": "ave", "street": "st", "road": "rd", "boulevard": "blvd",
        "lane": "ln", "terrace": "ter", "drive": "dr", "court": "ct",
        "place": "pl", "parkway": "pkwy", "highway": "hwy",
    }
    for a, b in replacements.items():
        value = re.sub(rf"\b{re.escape(a)}\b", b, value)
    return re.sub(r"\s+", " ", value).strip()


def strip_direction(value: str) -> str:
    value = normalize(value)
    value = re.sub(r"^(n|s|e|w|ne|nw|se|sw)\s+", "", value)
    value = re.sub(r"\s+(n|s|e|w|ne|nw|se|sw)$", "", value)
    return value.strip()


def load_pci_table(html: str) -> dict:
    match = re.search(r"const PCI_BY_NAME = (\{.*?\});", html, re.S)
    if not match:
        raise RuntimeError("PCI_BY_NAME was not found in templates/index.html")
    return json.loads(match.group(1))


def fetch_osm() -> dict:
    west, south, east, north = BOUNDS
    lon_step = (east - west) / TILE_COLS
    lat_step = (north - south) / TILE_ROWS
    elements = {}
    failures = []

    def fetch_tile(query: str):
        body = urllib.parse.urlencode({"data": query}).encode("utf-8")
        last_error = None
        for endpoint in OVERPASS_ENDPOINTS:
            try:
                request = urllib.request.Request(
                    endpoint,
                    data=body,
                    method="POST",
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": "StreetLens/1.0 build-pci-geojson",
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(request, timeout=30) as response:
                    return json.loads(response.read().decode("utf-8"))
            except Exception as exc:
                last_error = f"{endpoint}: {exc}"
        raise RuntimeError(last_error or "unknown Overpass error")

    for row in range(TILE_ROWS):
        tile_south = south + row * lat_step
        tile_north = north if row == TILE_ROWS - 1 else south + (row + 1) * lat_step
        for col in range(TILE_COLS):
            tile_west = west + col * lon_step
            tile_east = east if col == TILE_COLS - 1 else west + (col + 1) * lon_step
            query = make_query(tile_west, tile_south, tile_east, tile_north)
            try:
                data = fetch_tile(query)
                for element in data.get("elements", []):
                    element_id = element.get("id")
                    if element_id is not None:
                        elements[element_id] = element
            except Exception as exc:
                failures.append(f"tile {row + 1},{col + 1}: {exc}")
                print(f"Overpass tile failed: {failures[-1]}", file=sys.stderr)
            time.sleep(0.15)

    if not elements:
        # Deployment must not fail merely because Overpass is temporarily
        # unavailable. The browser/runtime endpoint can retry later.
        print(
            "Overpass unavailable during build; keeping existing embedded PCI geometry and continuing.",
            file=sys.stderr,
        )
        return {"elements": []}

    if failures:
        print(f"Overpass: {len(failures)} tile(s) failed; using successful tiles.", file=sys.stderr)
    return {"elements": list(elements.values())}


def main() -> None:
    html = TEMPLATE.read_text(encoding="utf-8")
    pci = load_pci_table(html)

    exact = {}
    base = {}
    for key, record in pci.items():
        exact[normalize(key)] = record
        base.setdefault(strip_direction(key), record)

    def find_record(name: str):
        return exact.get(normalize(name)) or base.get(strip_direction(name))

    data = fetch_osm()
    features = []
    seen = set()

    for way in data.get("elements", []):
        tags = way.get("tags") or {}
        osm_name = tags.get("name")
        geometry = way.get("geometry") or []
        if not osm_name or len(geometry) < 2:
            continue
        record = find_record(osm_name)
        if not record:
            continue

        key = f"{way.get('id')}:{record.get('name')}"
        if key in seen:
            continue
        seen.add(key)

        coords = [[p["lon"], p["lat"]] for p in geometry if "lon" in p and "lat" in p]
        if len(coords) < 2:
            continue

        features.append({
            "type": "Feature",
            "id": key,
            "properties": {
                "road": record.get("name"),
                "osmName": osm_name,
                "pci": float(record.get("pci", 0)),
                "condition": record.get("condition"),
                "treatment": record.get("treatment"),
                "records": json.dumps(record.get("records", []), separators=(",", ":")),
            },
            "geometry": {"type": "LineString", "coordinates": coords},
        })

    if not features:
        print(
            "No PCI-matched OSM segments were available during build; preserving the existing template and continuing.",
            file=sys.stderr,
        )
        return

    geojson = {"type": "FeatureCollection", "features": features}
    payload = json.dumps(geojson, separators=(",", ":"), ensure_ascii=False)

    marker = re.compile(
        r'const STREETLENS_PRELOADED_PCI = \{.*?\};',
        re.S,
    )
    replacement = f"const STREETLENS_PRELOADED_PCI = {payload};"
    updated, count = marker.subn(replacement, html, count=1)
    if count != 1:
        raise RuntimeError("STREETLENS_PRELOADED_PCI marker not found")

    TEMPLATE.write_text(updated, encoding="utf-8")
    print(f"StreetLens build: embedded {len(features)} PCI-matched OSM road segments for 109 evaluated roads.")


if __name__ == "__main__":
    main()
