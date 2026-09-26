from functools import wraps
import json
import os
import time
import urllib.parse
import urllib.request

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from models import User, db

load_dotenv()  # no-op on Vercel (env vars are injected directly); loads .env locally

app = Flask(__name__, static_folder="public/static")
app.config.from_object(Config)

db.init_app(app)

with app.app_context():
    # Idempotent: safe to call on every cold start. For anything beyond this
    # simple schema, switch to Flask-Migrate / Alembic instead.
    db.create_all()

# Small server-side OSM proxy for the StreetLens PCI map.
# The browser calls our own Vercel origin, avoiding cross-origin/rate-limit
# problems that can occur when the deployed browser calls Overpass directly.
OVERPASS_ENDPOINTS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
OVERPASS_QUERY = "[out:json][timeout:20];way[\"highway\"][\"name\"](39.910,-75.091,39.928,-75.062);out tags geom;"
_osm_cache = {"expires": 0, "data": None}

# Ordered ML inspection frames extracted from the Image Log spreadsheet.
# Load using an absolute path so this also works reliably inside Vercel's
# Python serverless runtime. The embedded fallback keeps the viewer populated
# even if a deployment/runtime has trouble reading the JSON metadata file.
ROAD_FRAMES_FALLBACK = [{'file': 'road_frames/road_001.png', 'frame': '001', 'source_frame': '0000', 'station_start': 0.0, 'station_end': 6.558, 'latitude': 39.71854080791789, 'longitude': -75.1446655020528}, {'file': 'road_frames/road_002.png', 'frame': '002', 'source_frame': '0001', 'station_start': 6.558, 'station_end': 13.117, 'latitude': 39.71854095623473, 'longitude': -75.14466568459657}, {'file': 'road_frames/road_003.png', 'frame': '003', 'source_frame': '0002', 'station_start': 13.117, 'station_end': 19.675, 'latitude': 39.7185417, 'longitude': -75.14466659999998}, {'file': 'road_frames/road_004.png', 'frame': '004', 'source_frame': '0003', 'station_start': 19.675, 'station_end': 26.233, 'latitude': 39.71854170000001, 'longitude': -75.1446666}, {'file': 'road_frames/road_005.png', 'frame': '005', 'source_frame': '0004', 'station_start': 26.233, 'station_end': 32.792, 'latitude': 39.71854170000002, 'longitude': -75.14466659999992}, {'file': 'road_frames/road_006.png', 'frame': '006', 'source_frame': '0005', 'station_start': 32.792, 'station_end': 39.35, 'latitude': 39.71854602, 'longitude': -75.14466243999999}, {'file': 'road_frames/road_007.png', 'frame': '007', 'source_frame': '0006', 'station_start': 39.35, 'station_end': 45.908, 'latitude': 39.71855160957447, 'longitude': -75.1446570574468}, {'file': 'road_frames/road_008.png', 'frame': '008', 'source_frame': '0007', 'station_start': 45.908, 'station_end': 52.467, 'latitude': 39.7185552, 'longitude': -75.1446536}, {'file': 'road_frames/road_009.png', 'frame': '009', 'source_frame': '0008', 'station_start': 52.467, 'station_end': 59.025, 'latitude': 39.71855519999999, 'longitude': -75.14465359999998}, {'file': 'road_frames/road_010.png', 'frame': '010', 'source_frame': '0009', 'station_start': 59.025, 'station_end': 65.583, 'latitude': 39.7185552, 'longitude': -75.1446536}, {'file': 'road_frames/road_011.png', 'frame': '011', 'source_frame': '0010', 'station_start': 65.583, 'station_end': 72.142, 'latitude': 39.7185552, 'longitude': -75.1446536}, {'file': 'road_frames/road_012.png', 'frame': '012', 'source_frame': '0011', 'station_start': 72.142, 'station_end': 78.7, 'latitude': 39.7185552, 'longitude': -75.1446536}, {'file': 'road_frames/road_013.png', 'frame': '013', 'source_frame': '0012', 'station_start': 78.7, 'station_end': 85.258, 'latitude': 39.7185552, 'longitude': -75.1446536}, {'file': 'road_frames/road_014.png', 'frame': '014', 'source_frame': '0013', 'station_start': 85.258, 'station_end': 91.817, 'latitude': 39.7185552, 'longitude': -75.14465359999998}, {'file': 'road_frames/road_015.png', 'frame': '015', 'source_frame': '0014', 'station_start': 91.817, 'station_end': 98.375, 'latitude': 39.71855678571428, 'longitude': -75.14465179142859}, {'file': 'road_frames/road_016.png', 'frame': '016', 'source_frame': '0015', 'station_start': 98.375, 'station_end': 104.933, 'latitude': 39.7185786507042, 'longitude': -75.14462685352116}, {'file': 'road_frames/road_017.png', 'frame': '017', 'source_frame': '0016', 'station_start': 104.933, 'station_end': 111.492, 'latitude': 39.71859927352939, 'longitude': -75.14460333235296}, {'file': 'road_frames/road_018.png', 'frame': '018', 'source_frame': '0017', 'station_start': 111.492, 'station_end': 118.05, 'latitude': 39.71861069999999, 'longitude': -75.14459030000002}, {'file': 'road_frames/road_019.png', 'frame': '019', 'source_frame': '0018', 'station_start': 118.05, 'station_end': 124.608, 'latitude': 39.71861069999999, 'longitude': -75.14459030000002}, {'file': 'road_frames/road_020.png', 'frame': '020', 'source_frame': '0019', 'station_start': 124.608, 'station_end': 131.167, 'latitude': 39.71861069999999, 'longitude': -75.14459030000003}, {'file': 'road_frames/road_021.png', 'frame': '021', 'source_frame': '0020', 'station_start': 131.167, 'station_end': 137.725, 'latitude': 39.71861069999998, 'longitude': -75.14459030000003}, {'file': 'road_frames/road_022.png', 'frame': '022', 'source_frame': '0021', 'station_start': 137.725, 'station_end': 144.283, 'latitude': 39.71861069999998, 'longitude': -75.14459030000003}, {'file': 'road_frames/road_023.png', 'frame': '023', 'source_frame': '0022', 'station_start': 144.283, 'station_end': 150.842, 'latitude': 39.71861069999998, 'longitude': -75.14459030000003}, {'file': 'road_frames/road_024.png', 'frame': '024', 'source_frame': '0023', 'station_start': 150.842, 'station_end': 157.4, 'latitude': 39.71861069999998, 'longitude': -75.14459030000003}, {'file': 'road_frames/road_025.png', 'frame': '025', 'source_frame': '0024', 'station_start': 157.4, 'station_end': 163.958, 'latitude': 39.71861069999998, 'longitude': -75.14459030000003}, {'file': 'road_frames/road_026.png', 'frame': '026', 'source_frame': '0025', 'station_start': 163.958, 'station_end': 170.517, 'latitude': 39.71861069999999, 'longitude': -75.14459030000002}, {'file': 'road_frames/road_027.png', 'frame': '027', 'source_frame': '0026', 'station_start': 170.517, 'station_end': 177.075, 'latitude': 39.7186234884058, 'longitude': -75.1445771}, {'file': 'road_frames/road_028.png', 'frame': '028', 'source_frame': '0027', 'station_start': 177.075, 'station_end': 183.633, 'latitude': 39.71870839428573, 'longitude': -75.14448946142859}, {'file': 'road_frames/road_029.png', 'frame': '029', 'source_frame': '0028', 'station_start': 183.633, 'station_end': 190.192, 'latitude': 39.71879348285715, 'longitude': -75.14440163428571}, {'file': 'road_frames/road_030.png', 'frame': '030', 'source_frame': '0029', 'station_start': 190.192, 'station_end': 196.75, 'latitude': 39.7188313, 'longitude': -75.14436260000001}, {'file': 'road_frames/road_031.png', 'frame': '031', 'source_frame': '0030', 'station_start': 196.75, 'station_end': 203.308, 'latitude': 39.7188313, 'longitude': -75.14436260000001}, {'file': 'road_frames/road_032.png', 'frame': '032', 'source_frame': '0031', 'station_start': 203.308, 'station_end': 209.867, 'latitude': 39.71883130000001, 'longitude': -75.14436260000001}, {'file': 'road_frames/road_033.png', 'frame': '033', 'source_frame': '0032', 'station_start': 209.867, 'station_end': 216.425, 'latitude': 39.71883130000001, 'longitude': -75.14436260000001}, {'file': 'road_frames/road_034.png', 'frame': '034', 'source_frame': '0033', 'station_start': 216.425, 'station_end': 222.983, 'latitude': 39.71883130000001, 'longitude': -75.14436260000001}, {'file': 'road_frames/road_035.png', 'frame': '035', 'source_frame': '0034', 'station_start': 222.983, 'station_end': 229.542, 'latitude': 39.71883130000001, 'longitude': -75.14436260000001}, {'file': 'road_frames/road_036.png', 'frame': '036', 'source_frame': '0035', 'station_start': 229.542, 'station_end': 236.1, 'latitude': 39.71883130000001, 'longitude': -75.14436260000001}, {'file': 'road_frames/road_037.png', 'frame': '037', 'source_frame': '0036', 'station_start': 236.1, 'station_end': 242.658, 'latitude': 39.7188313, 'longitude': -75.14436260000001}, {'file': 'road_frames/road_038.png', 'frame': '038', 'source_frame': '0037', 'station_start': 242.658, 'station_end': 249.217, 'latitude': 39.7188313, 'longitude': -75.14436260000001}, {'file': 'road_frames/road_039.png', 'frame': '039', 'source_frame': '0038', 'station_start': 249.217, 'station_end': 255.775, 'latitude': 39.71891342393163, 'longitude': -75.14426712564101}, {'file': 'road_frames/road_040.png', 'frame': '040', 'source_frame': '0039', 'station_start': 255.775, 'station_end': 262.333, 'latitude': 39.71888526691673, 'longitude': -75.14433490176295}, {'file': 'road_frames/road_041.png', 'frame': '041', 'source_frame': '0040', 'station_start': 262.333, 'station_end': 266.883, 'latitude': 39.71888546958509, 'longitude': -75.14433518637229}]
ROAD_FRAMES_META = os.path.join(
    app.root_path, "public", "static", "images", "road_frames", "road_frames.json"
)
ROAD_FRAMES = []
try:
    with open(ROAD_FRAMES_META, "r", encoding="utf-8") as fh:
        ROAD_FRAMES = json.load(fh)
except (OSError, ValueError, TypeError):
    ROAD_FRAMES = ROAD_FRAMES_FALLBACK

if not ROAD_FRAMES:
    ROAD_FRAMES = ROAD_FRAMES_FALLBACK


@app.route("/api/pci-roads")
def pci_roads():
    global _osm_cache
    now = time.time()
    if _osm_cache["data"] is not None and now < _osm_cache["expires"]:
        response = app.response_class(
            response=json.dumps(_osm_cache["data"]),
            status=200,
            mimetype="application/json",
        )
        response.headers["Cache-Control"] = "public, max-age=900, s-maxage=900"
        return response

    body = urllib.parse.urlencode({"data": OVERPASS_QUERY}).encode("utf-8")
    last_error = "unknown error"

    for endpoint in OVERPASS_ENDPOINTS:
        try:
            req = urllib.request.Request(
                endpoint,
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "StreetLens/1.0 pavement-condition-dashboard",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=24) as upstream:
                payload = upstream.read()
            data = json.loads(payload.decode("utf-8"))
            _osm_cache = {"expires": now + 900, "data": data}
            response = app.response_class(
                response=json.dumps(data),
                status=200,
                mimetype="application/json",
            )
            response.headers["Cache-Control"] = "public, max-age=900, s-maxage=900"
            return response
        except Exception as exc:
            last_error = f"{endpoint}: {exc}"
            continue

    return app.response_class(
        response=json.dumps({"error": "OSM road data unavailable", "detail": last_error}),
        status=502,
        mimetype="application/json",
    )


DISTRESS = [
    {"label": "Alligator crack", "pct": 62, "color": "#3b82f6", "sub": "Avg width 5mm · high density"},
    {"label": "Longitudinal", "pct": 21, "color": "#f97316", "sub": "Total length 8.5m · stable"},
    {"label": "Transverse", "pct": 11, "color": "#eab308", "sub": "4 cracks · 10m avg spacing"},
    {"label": "Pothole", "pct": 6, "color": "#a855f7", "sub": "1 count · 25mm depth"},
]
PILLS = [
    {"label": "Longitudinal", "score": 78},
    {"label": "Alligator", "score": 81},
    {"label": "Transverse", "score": 84},
    {"label": "Pothole", "score": 91},
]


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def root():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login_submit():
    identifier = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    user = User.query.filter(
        (User.username == identifier) | (User.email == identifier)
    ).first()

    if not user or not check_password_hash(user.password_hash, password):
        flash("Invalid username/email or password.", "error")
        return redirect(url_for("login"))

    session.clear()
    session["user_id"] = user.id
    session["username"] = user.username
    if request.form.get("remember"):
        session.permanent = True

    return redirect(url_for("dashboard"))


@app.route("/register", methods=["GET"])
def register_page():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/register", methods=["POST"])
def register():
    username = (request.form.get("username") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    if not username or not email or not password:
        flash("All fields are required.", "error")
        return redirect(url_for("login"))

    if len(username) < 3:
        flash("Username must be at least 3 characters.", "error")
        return redirect(url_for("login"))

    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("login"))

    if User.query.filter_by(username=username).first():
        flash("That username is already taken.", "error")
        return redirect(url_for("login"))

    if User.query.filter_by(email=email).first():
        flash("An account with that email already exists.", "error")
        return redirect(url_for("login"))

    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    db.session.commit()

    flash("Account created — you can sign in now.", "success")
    return redirect(url_for("login"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template(
        "index.html",
        screen="dashboard",
        distress=DISTRESS,
        pills=PILLS,
        username=session.get("username"),
        road_frames=ROAD_FRAMES,
        road_length_ft=(ROAD_FRAMES[-1]["station_end"] if ROAD_FRAMES else 0),
    )


if __name__ == "__main__":
    app.run(debug=True)
