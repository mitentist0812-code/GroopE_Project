from datetime import datetime

from apps.extensions import db


class RestaurantMenu(db.Model):
    __tablename__ = "restaurant_menu"
    __table_args__ = (
        db.CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_restaurant_menu_name",
        ),
        db.CheckConstraint(
            "price >= 0",
            name="ck_restaurant_menu_price",
        ),
        db.CheckConstraint(
            "calories >= 0",
            name="ck_restaurant_menu_calories",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(
        db.Integer,
        db.ForeignKey("account.id"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    calories = db.Column(db.Integer, nullable=False)


class RestaurantLocation(db.Model):
    __tablename__ = "restaurant_location"
    __table_args__ = (
        db.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_restaurant_location_latitude"),
        db.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_restaurant_location_longitude"),
    )

    restaurant_id = db.Column(db.Integer, db.ForeignKey("account.id"), primary_key=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)


class RestaurantPlaceClaim(db.Model):
    __tablename__ = "restaurant_place_claim"
    __table_args__ = (
        db.UniqueConstraint("account_id", name="uq_restaurant_place_claim_account"),
        db.CheckConstraint(
            "attempts >= 0 AND attempts <= 5",
            name="ck_restaurant_place_claim_attempts",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(
        db.Integer,
        db.ForeignKey("account.id"),
        nullable=False,
    )
    place_id = db.Column(db.String(256), nullable=False)
    code_hash = db.Column(db.String(64), nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)


class PlaceFavorite(db.Model):
    __tablename__ = "place_favorite"
    __table_args__ = (
        db.UniqueConstraint("account_id", "place_id", name="uq_place_favorite_account_place"),
        db.CheckConstraint(
            "length(place_id) >= 1 AND length(place_id) <= 256",
            name="ck_place_favorite_place_id_length",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("account.id"), nullable=False, index=True)
    place_id = db.Column(db.String(256), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)


class PlaceViewHistory(db.Model):
    __tablename__ = "place_view_history"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("account.id"), nullable=False, index=True)
    place_id = db.Column(db.String(256), nullable=False)
    viewed_at = db.Column(db.DateTime, nullable=False, default=datetime.now)


class Reservation(db.Model):
    __tablename__ = "reservation"
    __table_args__ = (
        db.CheckConstraint("guests >= 1 AND guests <= 20", name="ck_reservation_guests"),
        db.CheckConstraint(
            "status IN ('pending', 'confirmed', 'cancelled')",
            name="ck_reservation_status",
        ),
        db.UniqueConstraint("submission_key", name="uq_reservation_submission_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("account.id"), nullable=False, index=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("account.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    guests = db.Column(db.Integer, nullable=False)
    reserved_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    is_demo = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    submission_key = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    restaurant = db.relationship("Account", foreign_keys=[restaurant_id])
