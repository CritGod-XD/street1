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

BOUNDS = (-75.091, 39.910, -75.062, 39.928)
QUERY = (
    '[out:json][timeout:25];'
    f'way["highway"]["name"]({BOUNDS[1]},{BOUNDS[0]},{BOUNDS[3]},{BOUNDS[2]});'
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
    body = urllib.parse.urlencode({"data": QUERY}).encode("utf-8")
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
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = f"{endpoint}: {exc}"
            print(f"Overpass failed: {last_error}", file=sys.stderr)
            time.sleep(0.5)
    raise RuntimeError(f"All Overpass endpoints failed: {last_error}")


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
        raise RuntimeError("OSM returned zero PCI-matched road segments; refusing to overwrite the template")

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
