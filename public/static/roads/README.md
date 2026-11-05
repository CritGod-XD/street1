# StreetLens road datasets

Each road's inspection data lives in its own folder under `public/static/roads/`.

## Folder convention

Use a lowercase folder ID made from the road name, replacing spaces and punctuation with underscores:

```text
public/static/roads/
  README.md
  _template/
    README.md
  penn_ave_n_sample/
    index.json
    section_0001.png
    section_0001.json
    section_0002.png
    section_0002.json
    ...
  <road_folder_id>/
    index.json
    section_0001.png
    section_0001.json
    ...
```

The dashboard automatically looks for `/static/roads/<road_folder_id>/index.json` when a selected road has no frame list in the road registry. Penn Ave N keeps its existing `penn_ave_n_sample` folder ID.

## Upload a new road

1. Copy the structure described in `_template/README.md` and create a new folder for the road.
2. Put each inspection image and its matching annotation JSON beside `index.json`.
3. Use matching frame names, for example `section_0001.png` and `section_0001.json`.
4. Add each frame to `index.json`; set `image` and `annotation` to filenames relative to that index.
5. Ensure `road_name` matches the road name used by the map data. The folder ID must be its normalized lowercase underscore form.
6. Commit and push. No separate legacy image or annotation directories are needed.

The index loader resolves relative image and annotation paths against the index file, and loads only the selected road's frames as the viewer needs them.
