from datetime import datetime

from apps.extensions import db


class CalorieHistory(db.Model):
    __tablename__ = "calorie_history"
    __table_args__ = (
        db.UniqueConstraint("account_id", "save_key", name="uq_calorie_history_account_save_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("account.id"), nullable=False, index=True)
    save_key = db.Column(db.String(64), nullable=False)
    dish = db.Column(db.String(100), nullable=False)
    ingredients = db.Column(db.JSON, nullable=False)
    total_calories = db.Column(db.Integer)
    unmatched_count = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
