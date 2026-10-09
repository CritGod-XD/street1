# StreetLens

**Pavement Condition Monitoring & Roadway Analysis Platform**

StreetLens is a Flask web application for exploring pavement condition data geographically. It brings together PCI (Pavement Condition Index) scores, mapped street sections, distress categories, and pavement inspection imagery in one dashboard. The current dataset focuses on Collingswood, New Jersey, and includes a separate road-ranking page for the evaluated-road PCI list.

This README is intended for someone new to the project: it explains what the app does, how its pieces connect, how to run it locally, and where to make common changes.

## 1. What the application does

- **Dashboard (`/dashboard`)** — the main StreetLens workspace, with an interactive MapLibre map, pavement/road information, distress breakdown, and inspection imagery where available.
- **Interactive map** — pan and zoom, select mapped road sections, inspect information, reset the map, switch to satellite imagery, and open the expanded map view. Road overlays are styled by condition/metric using the bundled section data.
- **Road ranking (`/road-ranking`)** — a separate searchable and filterable ranking of the evaluated roads, ordered from the lowest PCI (worst condition) to the highest PCI (best condition). It reads `public/static/data/pci_evaluated_roads.json`.
- **Authentication** — login, registration, and logout routes protect dashboard pages.
- **Inspection imagery** — the uploaded `MDC Test Section` has 41 road-frame images and metadata. Other roads can show a pending/unavailable imagery state until their data and images are added.
- **Build-time map data** — a script prepares/validates the local map dataset for deployment so the application does not have to generate all map geometry during each page request.

> **Data distinction:** the map's segmented road data and the evaluated-road ranking dataset serve different purposes. The map data describes mapped street sections and their geometry; `pci_evaluated_roads.json` supplies the road-level PCI list used by the ranking page. Do not substitute one for the other without checking the expected schema.

## 2. Technology stack

- **Backend:** Python, Flask, Flask-SQLAlchemy
- **Templates/UI:** Jinja HTML templates and CSS
- **Map:** MapLibre GL JS; basemap styles/tiles are loaded from external map providers in the browser
- **Map data:** local JSON/GeoJSON-style section and road registry data
- **Database configuration:** SQLite by default for local development; PostgreSQL-compatible URL (for example, Neon) through `DATABASE_URL`
- **Hosting:** Vercel serverless deployment

Dependencies are listed in `requirements.txt`. MapLibre is loaded by the frontend, not installed as a Python package.

## 3. Repository layout

```text
street1-main/
├── app.py                         # Flask app, routes, authentication, page data
├── config.py                      # Secret/database configuration
├── models.py                      # SQLAlchemy models
├── requirements.txt               # Python dependencies
├── vercel.json                    # Vercel function and build configuration
├── scripts/
│   └── build_pci_geojson.py       # Build-time map-data validation/preparation
├── templates/
│   ├── index.html                 # Main dashboard and map UI
│   ├── login.html                 # Login page
│   ├── register.html              # Registration page
│   ├── road_ranking.html          # Evaluated-road PCI ranking UI
│   └── index_v4_backup.html       # Older backup template; not the main dashboard
└── public/static/
    ├── css/style.css              # Shared styling
    ├── js/app.js                  # Frontend interactions
    ├── data/
    │   ├── collingswood_sections.json  # Mapped street-run/section data
    │   ├── pci_evaluated_roads.json   # Road-level PCI ranking dataset
    │   ├── road_registry.json         # Uploaded road/frame registry
    │   └── sdi_by_name.json           # SDI values keyed by road name
    └── images/
        ├── crack-1.png, crack-2.png, crack-3.png  # Distress examples/assets
        ├── road_preview.png                       # Road preview image
        └── road_frames/                           # 41 inspection frames + metadata
```

## 4. How the workflow works

### A. Road-condition map

1. `templates/index.html` creates the MapLibre map and its controls.
2. The frontend loads the bundled mapped-section data from `public/static/data/collingswood_sections.json` (the build script helps prepare/validate the data used by the app).
3. Each section's geometry is drawn on the map. PCI/SDI values and condition categories determine its appearance and the information shown when a user hovers over or selects a section.
4. Selecting a section updates the relevant dashboard details. The map's road geometry and score records are data-driven; styling is controlled by the map layer definitions in the frontend.

### B. Road-ranking page

1. The user selects **Road Ranking** from the dashboard, or opens `/road-ranking` directly after logging in.
2. Flask's `road_ranking()` route in `app.py` reads `public/static/data/pci_evaluated_roads.json` and passes the data to `templates/road_ranking.html`.
3. The page displays the road-level records sorted by PCI from worst to best. Search and condition filters help narrow the list.
4. If the ranking list is empty, check that the JSON file is present in the deployment and that its field names match what `road_ranking.html` expects. Check Vercel build/runtime logs as well.

### C. Inspection frames

1. `public/static/data/road_registry.json` describes available roads and their frames.
2. `public/static/images/road_frames/road_frames.json` contains frame metadata; `road_001.png` through `road_041.png` are the current uploaded imagery.
3. When a selected road has available images, the dashboard can show its frames and related information. Roads without imagery should be represented as pending/unavailable rather than displaying unrelated frames.
4. To add a road, add its data and image files, update the registry and metadata consistently, and verify image paths resolve under `/static/images/...`.

### D. Authentication and data storage

- `/` redirects unauthenticated users to the login screen.
- `/login` accepts login credentials.
- `/register` provides account registration.
- `/logout` is a POST route that ends the session.
- `config.py` reads `SECRET_KEY` and `DATABASE_URL` from environment variables. Without `DATABASE_URL`, the app uses a local SQLite database (`local.db`).

## 5. Run locally

Use Python 3.12 if possible (the deployment setup targets Python 3.12).

### Windows PowerShell

```powershell
# From the project root
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Then open the local URL printed by Flask (commonly `http://127.0.0.1:5000`). If the app does not start, check the terminal traceback first. Do not commit `.env`, local databases, or secrets.

### Environment variables

Create a local `.env` file only if needed (keep it out of Git):

```env
SECRET_KEY=replace-with-a-long-random-secret
# Optional; omit to use local SQLite
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE
```

Use the actual connection string from your database provider. Never publish credentials in the README or source code. The fallback secret in `config.py` is for development only; set `SECRET_KEY` in Vercel for deployment.

## 6. Deploy to Vercel

1. Push the project to the connected GitHub repository.
2. In Vercel, confirm the correct repository and production branch are selected.
3. Set environment variables such as `SECRET_KEY` and, if using PostgreSQL, `DATABASE_URL` in Vercel Project Settings.
4. Keep the `vercel.json` build command configured to run `python scripts/build_pci_geojson.py`.
5. Deploy and inspect the build logs. Then test login, dashboard map loading, Road Ranking, and frame images on the deployed URL.

The build script validates/prepares bundled data; it does not prove that external map providers or every runtime route are reachable. The browser needs network access to the configured basemap provider for map tiles/styles.

## 7. Important data files and how to update them

| File | Purpose | When to edit |
|---|---|---|
| `collingswood_sections.json` | Mapped street sections and geometry/section properties | When the mapped-section dataset changes; regenerate through the project's data workflow rather than editing arbitrary coordinates by hand |
| `pci_evaluated_roads.json` | Road-level PCI values used for the ranking | When the evaluated-road PCI spreadsheet/list changes; preserve the expected keys and values |
| `sdi_by_name.json` | SDI values keyed by road name | When SDI source values change |
| `road_registry.json` | Roads with uploaded imagery and associated frame data | When adding/removing an imaged road or changing its frame list |
| `road_frames/road_frames.json` | Inspection frame metadata | When frame ordering, stationing, scores, coordinates, or filenames change |
| `road_frames/road_*.png` | Actual inspection images | When uploading or replacing road frames |
| `templates/road_ranking.html` | Ranking page layout and browser-side filtering/sorting presentation | When changing the ranking UI |
| `templates/index.html`, `public/static/css/style.css`, `public/static/js/app.js` | Dashboard UI, styles, and frontend behavior | When changing dashboard layout or interactions |
| `scripts/build_pci_geojson.py` | Build-time data generation/validation | When the build/data format changes |

**Keep schemas in sync.** When changing a JSON data structure, update the code that reads it and the build validator together. Then run the build command locally and inspect both the map and ranking pages.

## 8. PCI and distress colors

The ranking uses PCI condition classes and the StreetLens condition palette. The distress breakdown uses a separate category palette:

- Alligator crack — `#4A90C4`
- Longitudinal crack — `#C1543D`
- Transverse crack — `#D1A13C`
- Pothole — `#9370C4`

Distress colors identify *types of distress*; PCI colors represent the *overall condition category*. They are different legends and should not be interchanged.

## 9. Troubleshooting

**Road Ranking is empty**
- Confirm `public/static/data/pci_evaluated_roads.json` is present in the deployed project.
- Confirm the deployed `app.py` route and `templates/road_ranking.html` use the same schema/field names.
- Open the JSON file locally and verify it contains road records and PCI values.
- Check Vercel build and function logs after redeployment; a successful build alone does not guarantee runtime data loading.

**Map is blank or only the overlays are visible**
- Check browser console/network errors for MapLibre, style JSON, and tile requests.
- Verify that the browser can reach the configured basemap provider.
- Run the build script and verify the local section data is present.

**Inspection images do not appear**
- Check that the selected road is marked as having available imagery in `road_registry.json`.
- Verify filenames and case match the actual files under `public/static/images/road_frames/`.
- Open an image URL directly, for example `/static/images/road_frames/road_001.png`.

**Database/registration issues**
- Check `SECRET_KEY` and `DATABASE_URL` in the environment.
- Inspect Flask/Vercel logs for SQLAlchemy connection or table errors.
- For PostgreSQL providers, ensure the URL is valid and the database is reachable from the deployment environment.

## 10. Current scope and limitations

- The current project includes the Collingswood mapped-section dataset, a road-level PCI ranking JSON, and one road with 41 uploaded inspection frames.
- Mapped section count and unique evaluated-road count are different measures; don't assume every mapped section is a separate evaluated road.
- The map uses external basemap resources, so map appearance and availability depend partly on the configured provider/network.
- The README describes the repository's intended workflow; test the deployed Vercel app after changes to confirm runtime behavior.

## 11. Suggested first-time walkthrough

1. Install Python and the requirements.
2. Run the app locally and register/log in.
3. Open the dashboard and select/hover a colored road section.
4. Open the expanded map and try reset/satellite controls.
5. Use **Road Ranking** to search for a road and review its PCI position.
6. Inspect `pci_evaluated_roads.json` for the ranking source and `road_registry.json` plus `road_frames/` for image-linked roads.
7. Before committing changes, run `python scripts/build_pci_geojson.py` and check the relevant pages in the browser.

---

**Project:** StreetLens — Pavement Condition Monitoring & Roadway Analysis Platform  
**Primary application:** Flask + Jinja + MapLibre GL JS  
**Deployment target:** Vercel
