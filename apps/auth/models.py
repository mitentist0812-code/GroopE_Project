from datetime import datetime

from apps.extensions import db


class Account(db.Model):
    __tablename__ = "account"
    __table_args__ = (
        db.CheckConstraint(
            "account_type IN ('user', 'restaurant')",
            name="ck_account_account_type",
        ),
        db.UniqueConstraint("email", name="uq_account_email"),
        db.UniqueConstraint("place_id", name="uq_account_place_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    account_type = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200))
    phone = db.Column(db.String(30))
    place_id = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    preferences = db.relationship(
        "AccountPreference",
        back_populates="account",
        uselist=False,
        cascade="all, delete-orphan",
    )


class AccountPreference(db.Model):
    __tablename__ = "account_preference"

    account_id = db.Column(
        db.Integer,
        db.ForeignKey("account.id"),
        primary_key=True,
    )
    favorite_foods = db.Column(db.String(500), nullable=False, default="")
    disliked_foods = db.Column(db.String(500), nullable=False, default="")
    allergies = db.Column(db.JSON, nullable=False, default=list)
    religion = db.Column(db.String(20), nullable=False, default="")
    use_location = db.Column(db.Boolean, nullable=False, default=True)
    health_mode = db.Column(db.Boolean, nullable=False, default=False)
    autofill_email = db.Column(db.Boolean, nullable=False, default=False)
    account = db.relationship("Account", back_populates="preferences")
