#!/usr/bin/env python3
"""Validate the StreetLens deployment bundle before Vercel builds it.

The current dashboard builds its PCSI map directly from the geotagged road
registry in ``public/static/data/road_registry.json``.  It no longer needs an
Overpass request during the Vercel build.  Keeping the build offline makes the
deployment deterministic and avoids external API timeouts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "index.html"
REGISTRY = ROOT / "public" / "static" / "data" / "road_registry.json"
IMAGE_ROOT = ROOT / "public" / "static" / "images"


def main() -> None:
    if not TEMPLATE.is_file():
        raise RuntimeError(f"Missing dashboard template: {TEMPLATE}")
    if not REGISTRY.is_file():
        raise RuntimeError(f"Missing road registry: {REGISTRY}")

    html = TEMPLATE.read_text(encoding="utf-8")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    roads = registry.get("roads")
    if not isinstance(roads, list) or not roads:
        raise RuntimeError("road_registry.json does not contain any roads")

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

    # These are the markers required by the current dashboard JS.
    required_markers = (
        "let STREETLENS_ROAD_REGISTRY =",
        "let STREETLENS_ROADS =",
        "const STREETLENS_PRELOADED_PCI =",
        "const PCSI_COLORS =",
    )
    missing_markers = [m for m in required_markers if m not in html]
    if missing_markers:
        raise RuntimeError("Dashboard template is missing: " + ", ".join(missing_markers))

    # Keep the old build-time GeoJSON marker harmlessly present for compatibility
    # with older cached deployments; the current map does not depend on it.
    if not re.search(r"const STREETLENS_PRELOADED_PCI\s*=", html):
        raise RuntimeError("STREETLENS_PRELOADED_PCI marker is missing")

    pci_marker = re.search(r"const PCI_BY_NAME\s*=\s*(\{.*?\});", html, re.S)
    pci_count = 0
    if pci_marker:
        try:
            pci_count = len({str(v.get("name", "")) for v in json.loads(pci_marker.group(1)).values() if isinstance(v, dict) and v.get("name")})
        except Exception:
            pci_count = 0
    available = sum(1 for road in roads if road.get("status") == "available")
    print(
        "StreetLens build validation passed: "
        f"{pci_count} PCI records, {len(roads)} uploaded-road registry item(s), "
        f"{frame_count} frame(s), {available} road(s) with uploaded imagery. "
        "Map geometry is loaded from the existing OSM endpoint at runtime."
    )


if __name__ == "__main__":
    main()
