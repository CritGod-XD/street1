# StreetLens road-folder datasets

StreetLens supports a self-contained folder for each road. Keep each image beside
its matching LabelMe annotation JSON:

```text
public/static/roads/
  penn_ave_n_sample/
    section_0001.png
    section_0001.json
    section_0002.png
    section_0002.json
    index.json
  park_ave/
    frame_0001.png
    frame_0001.json
    index.json
```

## Generate the index

From the repository root:

```bash
python scripts/build_road_folder_index.py public/static/roads/penn_ave_n_sample --road-name "Penn Ave N"
```

The script pairs files by basename, for example `section_0001.png` with
`section_0001.json`. It writes `index.json` into that same folder. Images
without a matching JSON are retained in the index with a null annotation and
reported as warnings.

## Load the dataset

Pass the road's index URL to the existing viewer loader:

```js
window.streetLensLoadRoadDataset(
  '/static/roads/penn_ave_n_sample/index.json',
  'Penn Ave N'
);
```

The viewer resolves relative `image` and `annotation` filenames against the
index URL. Existing datasets whose index contains absolute `/static/...` paths
continue to work.

## Migration note

The existing Penn Ave N dataset is not moved by this code change. Migrate a
copy into the new folder first, generate its index, and test image/annotation
pairing before removing any old files. Keep road-level registry and PCI/SDI
metadata in their existing source until a separate migration is planned.
