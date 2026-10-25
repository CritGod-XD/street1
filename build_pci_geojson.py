#!/usr/bin/env python3
"""Validate the StreetLens deployment bundle before Vercel builds it.

The current dashboard builds its PCSI map directly from the geotagged road
registry in ``public/static/data/road_registry.json``.  It no longer needs an
Overpass request during the Vercel build.  Keeping the build offline makes the
deployment deterministic and avoids external API timeouts.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "index.html"
REGISTRY = ROOT / "public" / "static" / "data" / "road_registry.json"
SECTION_DATA = ROOT / "public" / "static" / "data" / "collingswood_sections.json"
IMAGE_ROOT = ROOT / "public" / "static" / "images"


def main() -> None:
    if not TEMPLATE.is_file():
        raise RuntimeError(f"Missing dashboard template: {TEMPLATE}")
    if not REGISTRY.is_file():
        raise RuntimeError(f"Missing road registry: {REGISTRY}")
    if not SECTION_DATA.is_file():
        raise RuntimeError(f"Missing segmented map data: {SECTION_DATA}")

    html = TEMPLATE.read_text(encoding="utf-8")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    section_data = json.loads(SECTION_DATA.read_text(encoding="utf-8"))

    roads = registry.get("roads")
    if not isinstance(roads, list) or not roads:
        raise RuntimeError("road_registry.json does not contain any roads")

    runs = section_data.get("runs")
    ring = section_data.get("ring")
    if not isinstance(runs, list) or not runs:
        raise RuntimeError("collingswood_sections.json does not contain any street runs")
    if not isinstance(ring, list) or len(ring) < 3:
        raise RuntimeError("collingswood_sections.json does not contain a valid map boundary")

    section_count = 0
    missing_geometry = 0
    for run in runs:
        sections = run.get("secs", [])
        if not isinstance(sections, list):
            raise RuntimeError(f"Invalid sections list for run {run.get('key')}")
        for section in sections:
            if not isinstance(section.get("g"), list) or len(section.get("g", [])) < 2:
                missing_geometry += 1
                continue
            section_count += 1

    if section_count == 0:
        raise RuntimeError("No usable section geometry was found")

    frame_count = 0
    missing_images: list[str] = []
    for road in roads:
        frames = road.get("frames", [])
        if not isinstance(frames, list):
            raise RuntimeError(f"Invalid frames list for road {road.get('road_id')}")
        frame_count += len(frames)
        for frame in frames:
            rel = str(frame.get("file", ""))
            if not rel:
                raise RuntimeError(f"Frame without image file in road {road.get('road_id')}")
            path = IMAGE_ROOT / rel
            if not path.is_file():
                missing_images.append(rel)

    if missing_images:
        sample = ", ".join(missing_images[:8])
        raise RuntimeError(f"Missing {len(missing_images)} road image(s): {sample}")

    # Keep validation aligned with the current MapLibre implementation.
    # The dashboard intentionally uses compact declarations such as
    # ``let STREETLENS_ROAD_REGISTRY={...}`` and renders sections through
    # ``addMapLayers``; the old validator looked for whitespace-sensitive
    # strings from an earlier implementation.
    required_markers = (
        "STREETLENS_ROAD_REGISTRY",
        "STREETLENS_SECTION_DATA",
        "function addMapLayers(",
        "collingswood_sections.json",
        "const STREETLENS_PCI_CLASSES",
        "const STREETLENS_SDI_CLASSES",
        "maplibregl.Map(",
    )
    missing_markers = [m for m in required_markers if m not in html]
    if missing_markers:
        raise RuntimeError("Dashboard template is missing: " + ", ".join(missing_markers))

    available = sum(1 for road in roads if road.get("status") == "available")
    print(
        "StreetLens build validation passed: "
        f"{len(runs)} street run(s), {section_count} mapped section(s), "
        f"{len(roads)} uploaded-road registry item(s), {frame_count} frame(s), "
        f"{available} road(s) with uploaded imagery. "
        f"{missing_geometry} section(s) without usable geometry were skipped. "
        "Segmented map data is bundled locally; no external map API is used during build."
    )


if __name__ == "__main__":
    main()
