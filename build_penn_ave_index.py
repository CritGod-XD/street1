#!/usr/bin/env python3
"""Build the Penn Ave N viewer index from the files present at build time.

Every image is indexed, even when its matching annotation JSON is absent.
In that case the image still appears in the viewer without an overlay.
Original images and annotation files are never modified.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "public" / "static" / "images" / "penn_ave_n_sample"
ANNOTATION_DIR = ROOT / "public" / "static" / "data" / "annotations" / "penn_ave_n_sample"
OUTPUT_FILE = ROOT / "public" / "static" / "data" / "penn_ave_n_sample_frames.json"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def natural_key(path: Path) -> list[Any]:
    """Sort section_2 before section_10 while preserving exact file names."""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", path.stem)]


def main() -> None:
    if not IMAGE_DIR.is_dir():
        raise SystemExit(
            f"Penn Ave N image folder not found: {IMAGE_DIR}\n"
            "Create this folder and add the road images before building."
        )
    if not ANNOTATION_DIR.is_dir():
        # The road images can still be shown without overlays.
        ANNOTATION_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(
        (p for p in IMAGE_DIR.iterdir()
         if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS),
        key=natural_key,
    )
    if not images:
        raise SystemExit(f"No road images found in {IMAGE_DIR}")

    annotations = {
        p.stem: p for p in ANNOTATION_DIR.iterdir()
        if p.is_file() and p.suffix.lower() == ".json"
    }

    frames: list[dict[str, Any]] = []
    matched_json: set[str] = set()
    invalid_json: list[str] = []
    missing_annotations: list[str] = []

    for image_path in images:
        annotation_path = annotations.get(image_path.stem)
        annotation_data: dict[str, Any] = {}
        annotation_url = None

        if annotation_path is not None:
            try:
                loaded = json.loads(annotation_path.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict):
                    raise ValueError("top-level JSON value is not an object")
                annotation_data = loaded
                annotation_url = (
                    "/static/data/annotations/penn_ave_n_sample/"
                    + annotation_path.name
                )
                matched_json.add(annotation_path.name)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                invalid_json.append(f"{annotation_path.name}: {exc}")
                # Do not point the viewer at invalid annotation data.
                annotation_url = None
        else:
            missing_annotations.append(image_path.name)

        match = re.search(r"\d+", image_path.stem)
        frame_number = match.group(0) if match else image_path.stem
        width = annotation_data.get("imageWidth", 1640)
        height = annotation_data.get("imageHeight", 787)
        try:
            width = int(width)
            height = int(height)
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
            "image": "/static/images/penn_ave_n_sample/" + image_path.name,
            "annotation": annotation_url,
            "image_width": width,
            "image_height": height,
            "shape_count": len(shapes),
        })

    unmatched_json = sorted(path.name for stem, path in annotations.items() if path.name not in matched_json)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps({
            "road_id": "penn-ave-n-sample",
            "road_name": "Penn Ave N",
            "source": "Generated automatically from the deployed image and annotation folders",
            "frame_count": len(frames),
            "frames": frames,
        }, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\nPenn Ave N index generated:")
    print(f"  Images discovered:                 {len(images)}")
    print(f"  Frames indexed (all images):       {len(frames)}")
    print(f"  Valid matching annotation files:   {len(matched_json)}")
    print(f"  Images without valid annotations:  {len(missing_annotations) + len(invalid_json)}")
    print(f"  JSON files without matched image:  {len(unmatched_json)}")
    print(f"  Output: {OUTPUT_FILE.relative_to(ROOT)}")
    if missing_annotations:
        print("\nImages without a matching JSON (still included in index):")
        for name in missing_annotations:
            print(f"  - {name}")
    if invalid_json:
        print("\nInvalid annotation JSON (images still included without overlays):")
        for item in invalid_json:
            print(f"  - {item}")
    if unmatched_json:
        print("\nJSON files without a matching image:")
        for name in unmatched_json:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
