from datetime import datetime

from apps.extensions import db


class ContentReview(db.Model):
    __tablename__ = "content_review"
    __table_args__ = (
        db.CheckConstraint(
            "(recipe_id IS NOT NULL AND place_id IS NULL) OR "
            "(recipe_id IS NULL AND place_id IS NOT NULL)",
            name="ck_content_review_single_target",
        ),
        db.CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name="ck_content_review_rating",
        ),
        db.CheckConstraint(
            "length(trim(comment)) > 0",
            name="ck_content_review_comment",
        ),
        db.Index(
            "uq_content_review_account_recipe",
            "account_id",
            "recipe_id",
            unique=True,
            sqlite_where=db.text("recipe_id IS NOT NULL"),
            postgresql_where=db.text("recipe_id IS NOT NULL"),
        ),
        db.Index(
            "uq_content_review_account_place",
            "account_id",
            "place_id",
            unique=True,
            sqlite_where=db.text("place_id IS NOT NULL"),
            postgresql_where=db.text("place_id IS NOT NULL"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(
        db.Integer,
        db.ForeignKey("account.id"),
        nullable=False,
    )
    recipe_id = db.Column(
        db.Integer,
        db.ForeignKey("recipe_list.id"),
        nullable=True,
        index=True,
    )
    place_id = db.Column(db.String(256), nullable=True, index=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
    )
    account = db.relationship("Account")
    recipe = db.relationship("Recipe_list")
