
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


# ==================================
# ユーザー情報
# ==================================
class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )


# ==================================
# レシピ情報
# ==================================
class Recipe_list(db.Model):
    __tablename__ = "recipe_list"

    id = db.Column(db.Integer, primary_key=True)

    recipe_name = db.Column(
        db.String(100),
        nullable=False
    )

    ingredients = db.Column(
        db.Text,
        nullable=False
    )

    description = db.Column(
        db.Text,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.now
    )


# ==================================
# レシピ閲覧履歴
# ==================================
class Search_history(db.Model):
    __tablename__ = "search_history"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True
    )

    recipe_id = db.Column(
        db.Integer,
        db.ForeignKey("recipe_list.id"),
        nullable=False
    )

    viewed_at = db.Column(
        db.DateTime,
        default=datetime.now
    )


# ==================================
# お気に入り情報
# ==================================
class Favorite(db.Model):
    __tablename__ = "favorite"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    recipe_id = db.Column(
        db.Integer,
        db.ForeignKey("recipe_list.id"),
        nullable=False
    )

    # 同じユーザーの重複登録を防止
    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "recipe_id",
            name="unique_favorite"
        ),
    )


# ==================================
# レビュー情報
# ==================================
class Review(db.Model):
    __tablename__ = "review"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    recipe_id = db.Column(
        db.Integer,
        db.ForeignKey("recipe_list.id"),
        nullable=False
    )

    # 星評価（1～5）
    rating = db.Column(
        db.Integer,
        nullable=False
    )

    # レビューコメント
    comment = db.Column(
        db.Text,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.now
    )

