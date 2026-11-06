#!/usr/bin/env python3
"""Build the Penn Ave N index from its canonical self-contained road folder.

Expected layout:
  public/static/roads/penn_ave_n_sample/
    index.json
    section_0001.png
    section_0001.json
    ...

The generated index uses paths relative to the road folder, matching the
shared StreetLens road-folder loader. Images without annotations remain
available in the viewer; source images and JSON files are never modified.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROAD_DIR = ROOT / "public" / "static" / "roads" / "penn_ave_n_sample"
OUTPUT_FILE = ROAD_DIR / "index.json"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def natural_key(path: Path) -> list[Any]:
    """Sort section_2 before section_10 while preserving exact file names."""
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.stem)
    ]


def main() -> None:
    if not ROAD_DIR.is_dir():
        raise SystemExit(f"Penn Ave N road folder not found: {ROAD_DIR}")

    images = sorted(
        (
            path for path in ROAD_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ),
        key=natural_key,
    )
    if not images:
        raise SystemExit(f"No road images found in {ROAD_DIR}")

    frames: list[dict[str, Any]] = []
    missing_annotations: list[str] = []
    invalid_annotations: list[str] = []

    for image_path in images:
        annotation_path = image_path.with_suffix(".json")
        annotation_name = annotation_path.name if annotation_path.is_file() else None
        annotation_data: dict[str, Any] = {}

        if annotation_name:
            try:
                loaded = json.loads(annotation_path.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict):
                    raise ValueError("top-level JSON value is not an object")
                annotation_data = loaded
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                invalid_annotations.append(f"{annotation_path.name}: {exc}")
                annotation_name = None
        else:
            missing_annotations.append(image_path.name)

        match = re.search(r"\d+", image_path.stem)
        frame_number = match.group(0) if match else image_path.stem

        width = annotation_data.get("imageWidth", 1640)
        height = annotation_data.get("imageHeight", 787)
        try:
            width, height = int(width), int(height)
            if width <= 0 or height <= 0:
                raise ValueError
        except (TypeError, ValueError):
            width, height = 1640, 787

        shapes = annotation_data.get("shapes", [])
        if not isinstance(shapes, list):
            shapes = []

        frames.append({
            "frame_id": image_path.stem,
            "frame": frame_number,
            "image": image_path.name,
            "annotation": annotation_name,
            "image_width": width,
            "image_height": height,
            "shape_count": len(shapes) if annotation_name else None,
        })

    index = {
        "version": 1,
        "format": "streetlens-road-folder",
        "road_id": "penn-ave-n-sample",
        "road_name": "Penn Ave N",
        "source": "Generated from co-located Penn Ave N images and annotation JSON files",
        "frame_count": len(frames),
        "frames": frames,
    }

    OUTPUT_FILE.write_text(
        json.dumps(index, indent=2) + "\n",
        encoding="utf-8",
    )

    valid_annotations = sum(1 for frame in frames if frame["annotation"])
    print("Penn Ave N road-folder index generated:")
    print(f"  Images discovered:                {len(images)}")
    print(f"  Frames indexed:                   {len(frames)}")
    print(f"  Valid matching annotations:       {valid_annotations}")
    print(f"  Images without valid annotations: {len(missing_annotations) + len(invalid_annotations)}")
    print(f"  Output: {OUTPUT_FILE.relative_to(ROOT)}")

    if missing_annotations:
        print("\nImages without a matching JSON (still included):")
        for name in missing_annotations:
            print(f"  - {name}")
    if invalid_annotations:
        print("\nInvalid annotation JSON (images still included without overlays):")
        for item in invalid_annotations:
            print(f"  - {item}")


if __name__ == "__main__":
    main()
