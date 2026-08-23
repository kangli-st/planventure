import os
import re

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import create_access_token, get_jwt_identity

from extensions import db, jwt

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", app.config["SECRET_KEY"])
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///planventure.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
CORS(
    app,
    resources={
        r"/*": {"origins": [o.strip() for o in cors_origins.split(",")]},
    },
)

db.init_app(app)
jwt.init_app(app)

from models import User, hash_password  # noqa: E402


def create_token(user_id: int) -> str:
    """Create a signed JWT for a user."""
    return create_access_token(identity=str(user_id))


def get_current_user_id() -> str:
    """Return the current authenticated user id from the token."""
    return get_jwt_identity()


def is_valid_email(email: str) -> bool:
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return re.match(pattern, email) is not None


@app.route("/")
def home():
    return jsonify({"message": "Welcome to PlanVenture API"})


@app.route("/health")
def health_check():
    return jsonify({"status": "healthy"})


@app.route("/auth/register", methods=["POST"])
def register_user():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if not is_valid_email(email):
        return jsonify({"error": "Invalid email format"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    user = User(email=email)
    user.password_hash = hash_password(password)
    db.session.add(user)
    db.session.commit()

    token = create_token(user.id)
    return jsonify({"message": "User registered successfully", "access_token": token}), 201


@app.route("/auth/login", methods=["POST"])
def login_user():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if not is_valid_email(email):
        return jsonify({"error": "Invalid email format"}), 400

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_token(user.id)
    return jsonify(
        {
            "message": "Login successful",
            "access_token": token,
            "user": {"id": user.id, "email": user.email},
        }
    ), 200


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
