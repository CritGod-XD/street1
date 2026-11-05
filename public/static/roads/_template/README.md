# New road dataset template

Create one folder per road under `public/static/roads/`, named with the normalized road name (lowercase; spaces and punctuation become underscores).

## Required layout

```text
<road_folder_id>/
  index.json
  section_0001.png
  section_0001.json
  section_0002.png
  section_0002.json
  ...
```

Keep each image and its annotation JSON together in this folder. The image and JSON must use the same frame number. Do not put copies in `public/static/images/` or `public/static/data/annotations/`.

## index.json format

```json
{
  "version": 1,
  "format": "streetlens-road-folder",
  "road_id": "example-road",
  "road_name": "Example Road",
  "frame_count": 2,
  "frames": [
    {
      "frame_id": "section_0001",
      "frame": "0001",
      "image": "section_0001.png",
      "annotation": "section_0001.json",
      "image_width": 1640,
      "image_height": 787,
      "shape_count": 0
    },
    {
      "frame_id": "section_0002",
      "frame": "0002",
      "image": "section_0002.png",
      "annotation": "section_0002.json",
      "image_width": 1640,
      "image_height": 787,
      "shape_count": 0
    }
  ]
}
```

Set `frame_count` to the number of entries in `frames`. Update dimensions and shape counts to match your files. Annotation JSON should use the StreetLens annotation schema (including `imageWidth`, `imageHeight`, and `shapes`). The road name must match the map's road name so the dashboard can find the folder automatically.
