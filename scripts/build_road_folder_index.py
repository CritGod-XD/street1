#!/usr/bin/env python3
"""Build an index.json for a self-contained StreetLens road folder.

Expected layout:
  public/static/roads/penn_ave_n_sample/
    section_0001.png
    section_0001.json
    section_0002.png
    section_0002.json

Run:
  python scripts/build_road_folder_index.py public/static/roads/penn_ave_n_sample
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def image_dimensions(path: Path) -> tuple[int | None, int | None]:
    """Read PNG dimensions without requiring Pillow."""
    if path.suffix.lower() == ".png":
        try:
            with path.open("rb") as stream:
                header = stream.read(24)
            if header[:8] == b"\x89PNG\r\n\x1a\n":
                return struct.unpack(">II", header[16:24])
        except OSError:
            pass
    return None, None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("road_folder", type=Path, help="Folder containing paired image and JSON files")
    parser.add_argument("--road-id", help="Optional stable road identifier")
    parser.add_argument("--road-name", help="Display name for the road")
    args = parser.parse_args()

    folder = args.road_folder.resolve()
    if not folder.is_dir():
        raise SystemExit(f"Road folder does not exist: {folder}")

    frames = []
    missing_annotations = []
    for image in sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS):
        annotation = image.with_suffix(".json")
        width, height = image_dimensions(image)
        frame = {
            "frame_id": image.stem,
            "frame": image.stem,
            "image": image.name,
            "annotation": annotation.name if annotation.is_file() else None,
        }
        if width and height:
            frame["image_width"] = width
            frame["image_height"] = height
        if annotation.is_file():
            try:
                payload = json.loads(annotation.read_text(encoding="utf-8"))
                frame["shape_count"] = len(payload.get("shapes", []))
            except (OSError, json.JSONDecodeError, AttributeError):
                frame["shape_count"] = None
        else:
            missing_annotations.append(image.name)
        frames.append(frame)

    index = {
        "version": 1,
        "format": "streetlens-road-folder",
        "road_id": args.road_id or folder.name,
        "road_name": args.road_name or folder.name.replace("_", " ").title(),
        "source": "Generated from co-located road images and matching annotation JSON files",
        "frame_count": len(frames),
        "frames": frames,
    }
    output = folder / "index.json"
    output.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output} with {len(frames)} frame(s).")
    if missing_annotations:
        print(f"Warning: {len(missing_annotations)} image(s) have no matching JSON annotation:")
        for name in missing_annotations[:20]:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
