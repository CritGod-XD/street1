# StreetLens road datasets

Each physical street has one canonical folder. Alternate survey labels for the same street resolve through `/static/js/road-datasets.js`. Original map run labels and PCI/SDI values remain unchanged. Penn Ave N keeps its existing dataset folder. Add images and matching LabelMe JSON annotations to a road folder and generate its `index.json` with `scripts/build_road_folder_index.py`.
