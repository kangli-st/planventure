import os
import re
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import create_access_token, get_jwt_identity, verify_jwt_in_request

from extensions import db, jwt
from trip_routes import trip_bp

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", app.config["SECRET_KEY"])
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///planventure.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173")
allowed_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
CORS(
    app,
    resources={
        r"/*": {
            "origins": allowed_origins,
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        },
    },
    supports_credentials=True,
)

db.init_app(app)
jwt.init_app(app)
app.register_blueprint(trip_bp)

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


def auth_required(view_fn):
    """Middleware-style decorator that requires a valid JWT on the route."""

    @wraps(view_fn)
    def wrapped(*args, **kwargs):
        verify_jwt_in_request()
        return view_fn(*args, **kwargs)

    return wrapped


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


@app.route("/auth/me", methods=["GET"])
@auth_required
def auth_me():
    user_id = int(get_current_user_id())
    user = User.query.get(user_id)
    if user is None:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"user": {"id": user.id, "email": user.email}}), 200


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
