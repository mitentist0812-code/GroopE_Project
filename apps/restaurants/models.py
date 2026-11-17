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
