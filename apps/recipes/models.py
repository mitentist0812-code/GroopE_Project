
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


# レシピ情報を管理するテーブル
class Recipe_list(db.Model):
    __tablename__ = "recipe_list"

    id = db.Column(db.Integer, primary_key=True)
    recipe_name = db.Column(db.String(100), nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
