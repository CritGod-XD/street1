from functools import wraps
import json
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
# The JSON keeps the viewer easy to replace later with an API-backed frame list.
ROAD_FRAMES = []
ROAD_FRAMES_META = app.static_folder + "/images/road_frames/road_frames.json"
try:
    with open(ROAD_FRAMES_META, "r", encoding="utf-8") as fh:
        ROAD_FRAMES = json.load(fh)
except (OSError, ValueError):
    ROAD_FRAMES = []


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
