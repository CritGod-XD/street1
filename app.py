from functools import wraps

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
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("index.html", screen="login")


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
    )


if __name__ == "__main__":
    app.run(debug=True)
