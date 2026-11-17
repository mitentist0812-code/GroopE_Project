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
