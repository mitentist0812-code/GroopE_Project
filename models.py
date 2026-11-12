from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# ユーザー関連
class User(db.Model):
    __tablename__ = "User"
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)  # パスワードハッシュを保存
    user_name = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    religion = db.Column(db.String(100))
    health_mode = db.Column(db.Boolean, nullable=False, default=False)


class FoodPreference(db.Model):
    __tablename__ = "FoodPreference"
    food_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    food_name = db.Column(db.String(100), nullable=False, unique=True)


class UserFoodPreference(db.Model):
    __tablename__ = "UserFoodPreference"
    user_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), primary_key=True)
    food_id = db.Column(db.Integer, db.ForeignKey("FoodPreference.food_id"), primary_key=True)
    preference_type = db.Column(db.String(10), nullable=False)


class Allergen(db.Model):
    __tablename__ = "Allergen"
    allergy_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    allergy_name = db.Column(db.String(50), nullable=False, unique=True)


class UserAllergen(db.Model):
    __tablename__ = "UserAllergen"
    user_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), primary_key=True)
    allergen_id = db.Column(db.Integer, db.ForeignKey("Allergen.allergy_id"), primary_key=True)


# 店舗・メニュー関連
class RestaurantAccount(db.Model):
    __tablename__ = "RestaurantAccount"
    restaurant_account_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    account_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)  # パスワードハッシュを保存
    address = db.Column(db.String(500))
    phone_number = db.Column(db.String(30))
    closed = db.Column(db.String(15))
    parking = db.Column(db.Boolean, nullable=False, default=False)
    smoking = db.Column(db.Boolean, nullable=False, default=False)


class Restaurant(db.Model):
    __tablename__ = "Restaurant"
    # 設計書に主キーがないため store_id を追加
    store_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    place_id = db.Column(db.String(255), unique=True)
    restaurant_account_id = db.Column(db.Integer, db.ForeignKey("RestaurantAccount.restaurant_account_id"), nullable=False)
    store_name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(500))
    business_hours = db.Column(db.Text)
    parking_info = db.Column(db.String(255))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)


class Genre(db.Model):
    __tablename__ = "Genre"
    genre_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    genre_name = db.Column(db.String(50), nullable=False, unique=True)


class Menu(db.Model):
    __tablename__ = "Menu"
    menu_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("Restaurant.store_id"), nullable=False)
    menu_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False, default=0)
    calories = db.Column(db.Integer)


# 検索・お気に入り・レビュー関連
class SearchHistory(db.Model):
    __tablename__ = "SearchHistory"
    search_history_id = db.Column(db.Integer,primary_key=True,autoincrement=True)
    user_id = db.Column(db.Integer,db.ForeignKey("User.user_id"),nullable=False)
    restaurant_id = db.Column(db.Integer,db.ForeignKey("Restaurant.store_id"),nullable=True)
    recipe_id = db.Column(db.Integer,db.ForeignKey("Recipe.recipe_id"),nullable=True)
    searched_at = db.Column(db.DateTime,nullable=False,default=datetime.utcnow)



class Favorite(db.Model):
    __tablename__ = "Favorite"
    user_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("Restaurant.store_id"), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Review(db.Model):
    __tablename__ = "Review"
    review_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("Restaurant.store_id"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


# 予約関連
class Reservation(db.Model):
    __tablename__ = "Reservation"
    reservation_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("Restaurant.store_id"),primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), nullable=False)
    reservation_datetime = db.Column(db.DateTime, nullable=False)
    party_size = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    request_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class ReservationHistory(db.Model):
    __tablename__ = "ReservationHistory"
    reservation_history_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey("Reservation.reservation_id"), nullable=False)
    previous_status = db.Column(db.String(20))
    new_status = db.Column(db.String(20), nullable=False)
    change_note = db.Column(db.String(255))
    changed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


# レシピ・冷蔵庫画像関連
class Recipe(db.Model):
    __tablename__ = "Recipe"
    recipe_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), nullable=False)
    recipe_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    cooking_time_minutes = db.Column(db.Integer)
    is_public = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class RecipeIngredient(db.Model):
    __tablename__ = "RecipeIngredient"
    recipe_ingredients_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("Recipe.recipe_id"), nullable=False)
    ingredient_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.String(100), nullable=False)


class FridgeImage(db.Model):
    __tablename__ = "FridgeImage"
    fridge_image_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), nullable=False)
    image_path = db.Column(db.String(500), nullable=False)
    recognition_status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class FridgeIngredient(db.Model):
    __tablename__ = "FridgeIngredient"
    fridge_ingredients_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fridge_image_id = db.Column(db.Integer, db.ForeignKey("FridgeImage.fridge_image_id"), nullable=False)
    ingredient_name = db.Column(db.String(100), nullable=False)
    confidence = db.Column(db.Float)
    is_confirmed = db.Column(db.Boolean, nullable=False, default=False)


# カロリー推定関連
class CalorieEstimation(db.Model):
    __tablename__ = "CalorieEstimation"
    estimation_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    dish_name = db.Column(db.String(100), nullable=False)
    estimated_calories = db.Column(db.Integer, nullable=False)
    estimated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(15), nullable=False, default="pending")
