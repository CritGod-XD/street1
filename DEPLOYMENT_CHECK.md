# StreetLens Vercel Deployment Check

Validated locally before push:

- Python source files compile successfully.
- `scripts/build_pci_geojson.py` completes without external network calls.
- `road_registry.json` contains 1 configured road and 41 inspection frames.
- All 41 referenced road images exist under `public/static/images/road_frames/`.
- Jinja dashboard renders with the road registry injected.
- Rendered dashboard JavaScript passes Node syntax validation.
- `public/static/js/app.js` passes Node syntax validation.
- `requirements.txt` includes `psycopg[binary]` for Neon/PostgreSQL.
- `.python-version` pins Python 3.12.
- `vercel.json` runs the offline validation build command.

## Required Vercel environment variables

Set these in Vercel Project Settings → Environment Variables:

- `DATABASE_URL` — Neon/PostgreSQL connection string.
- `SECRET_KEY` — a long random production secret.

Do not commit `.env` or database credentials.

## Expected build

```text
Running "python scripts/build_pci_geojson.py"
StreetLens build validation passed: 1 road(s), 41 frame(s), 1 road(s) with uploaded imagery. No external map API required.
Build Completed
```

The current PCSI map is generated from the geotagged road registry in the deployed static data. It does not require Overpass during the Vercel build.


## Runtime fix (Vercel)
- Database initialization is lazy; importing `app.py` no longer calls `db.create_all()`.
- This prevents a missing/unavailable database from crashing every Vercel route at cold start.
- Vercel uses `/tmp/streetlens.db` only as a fallback when `DATABASE_URL` is absent. For persistent accounts, configure `DATABASE_URL` to Neon/Postgres.
- Authentication requests initialize the schema only when needed and log the actual database exception if initialization fails.
