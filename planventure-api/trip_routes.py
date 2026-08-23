from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from extensions import db
from models import Trip

trip_bp = Blueprint("trip", __name__, url_prefix="/trip")


def _serialize_trip(trip: Trip) -> dict:
    return {
        "id": trip.id,
        "user_id": trip.user_id,
        "destination": trip.destination,
        "start_date": trip.start_date.isoformat(),
        "end_date": trip.end_date.isoformat(),
        "latitude": trip.latitude,
        "longitude": trip.longitude,
        "itinerary": trip.itinerary,
        "created_at": trip.created_at.isoformat() if trip.created_at else None,
        "updated_at": trip.updated_at.isoformat() if trip.updated_at else None,
    }


def _parse_date(date_str: str, field_name: str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date(), None
    except ValueError:
        return None, f"{field_name} must be in YYYY-MM-DD format"


def generate_default_itinerary_template(destination: str, start_date, end_date) -> str:
    """Generate a simple day-by-day itinerary template."""
    total_days = (end_date - start_date).days + 1

    lines = [
        f"Trip to {destination}",
        f"Duration: {total_days} day(s)",
        "",
    ]

    for day_number in range(1, total_days + 1):
        lines.extend(
            [
                f"Day {day_number}:",
                "- Morning: ",
                "- Afternoon: ",
                "- Evening: ",
                "- Notes: ",
                "",
            ]
        )

    return "\n".join(lines).strip()


@trip_bp.route("", methods=["GET"])
def list_trips():
    # Optional JWT: if present return only the caller's trips, otherwise return an empty list.
    verify_jwt_in_request(optional=True)
    current_user_id = get_jwt_identity()

    if current_user_id is None:
        return jsonify({"trips": []}), 200

    trips = Trip.query.filter_by(user_id=int(current_user_id)).order_by(Trip.start_date.asc()).all()
    return jsonify({"trips": [_serialize_trip(trip) for trip in trips]}), 200


@trip_bp.route("/<int:trip_id>", methods=["GET"])
def get_trip(trip_id: int):
    verify_jwt_in_request()
    current_user_id = int(get_jwt_identity())

    trip = Trip.query.filter_by(id=trip_id, user_id=current_user_id).first()
    if trip is None:
        return jsonify({"error": "Trip not found"}), 404

    return jsonify({"trip": _serialize_trip(trip)}), 200


@trip_bp.route("", methods=["POST"])
def create_trip():
    verify_jwt_in_request()
    current_user_id = int(get_jwt_identity())

    data = request.get_json(silent=True) or {}
    destination = (data.get("destination") or "").strip()
    start_date_str = (data.get("start_date") or "").strip()
    end_date_str = (data.get("end_date") or "").strip()

    if not destination or not start_date_str or not end_date_str:
        return jsonify({"error": "destination, start_date, and end_date are required"}), 400

    start_date, start_error = _parse_date(start_date_str, "start_date")
    if start_error:
        return jsonify({"error": start_error}), 400

    end_date, end_error = _parse_date(end_date_str, "end_date")
    if end_error:
        return jsonify({"error": end_error}), 400

    if end_date < start_date:
        return jsonify({"error": "end_date cannot be earlier than start_date"}), 400

    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if latitude is not None:
        try:
            latitude = float(latitude)
        except (TypeError, ValueError):
            return jsonify({"error": "latitude must be a valid number"}), 400

    if longitude is not None:
        try:
            longitude = float(longitude)
        except (TypeError, ValueError):
            return jsonify({"error": "longitude must be a valid number"}), 400

    itinerary = data.get("itinerary")
    if itinerary is None or not str(itinerary).strip():
        itinerary = generate_default_itinerary_template(destination, start_date, end_date)

    trip = Trip(
        user_id=current_user_id,
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        latitude=latitude,
        longitude=longitude,
        itinerary=itinerary,
    )

    db.session.add(trip)
    db.session.commit()

    return jsonify({"message": "Trip created successfully", "trip": _serialize_trip(trip)}), 201


@trip_bp.route("/<int:trip_id>", methods=["PUT"])
def update_trip(trip_id: int):
    verify_jwt_in_request()
    current_user_id = int(get_jwt_identity())

    trip = Trip.query.filter_by(id=trip_id, user_id=current_user_id).first()
    if trip is None:
        return jsonify({"error": "Trip not found"}), 404

    data = request.get_json(silent=True) or {}

    if "destination" in data:
        destination = (data.get("destination") or "").strip()
        if not destination:
            return jsonify({"error": "destination cannot be empty"}), 400
        trip.destination = destination

    if "start_date" in data:
        start_date, start_error = _parse_date((data.get("start_date") or "").strip(), "start_date")
        if start_error:
            return jsonify({"error": start_error}), 400
        trip.start_date = start_date

    if "end_date" in data:
        end_date, end_error = _parse_date((data.get("end_date") or "").strip(), "end_date")
        if end_error:
            return jsonify({"error": end_error}), 400
        trip.end_date = end_date

    if trip.end_date < trip.start_date:
        return jsonify({"error": "end_date cannot be earlier than start_date"}), 400

    if "latitude" in data:
        latitude = data.get("latitude")
        if latitude is None:
            trip.latitude = None
        else:
            try:
                trip.latitude = float(latitude)
            except (TypeError, ValueError):
                return jsonify({"error": "latitude must be a valid number"}), 400

    if "longitude" in data:
        longitude = data.get("longitude")
        if longitude is None:
            trip.longitude = None
        else:
            try:
                trip.longitude = float(longitude)
            except (TypeError, ValueError):
                return jsonify({"error": "longitude must be a valid number"}), 400

    if "itinerary" in data:
        trip.itinerary = data.get("itinerary")

    db.session.commit()

    return jsonify({"message": "Trip updated successfully", "trip": _serialize_trip(trip)}), 200


@trip_bp.route("/<int:trip_id>", methods=["DELETE"])
def delete_trip(trip_id: int):
    verify_jwt_in_request()
    current_user_id = int(get_jwt_identity())

    trip = Trip.query.filter_by(id=trip_id, user_id=current_user_id).first()
    if trip is None:
        return jsonify({"error": "Trip not found"}), 404

    db.session.delete(trip)
    db.session.commit()

    return jsonify({"message": "Trip deleted successfully"}), 200
