from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<User {self.username}>"



class ScoreRevision(db.Model):
    __tablename__ = "score_revisions"

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(160), nullable=False)
    source = db.Column(db.String(40), nullable=False, default="manual")
    scores_json = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<ScoreRevision {self.id} {self.label}>"
