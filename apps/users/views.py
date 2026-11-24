import re
from urllib.error import URLError

from flask import (
    Blueprint,
    current_app,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload

from apps.auth.models import Account
from apps.extensions import db
from apps.home.places import PlacesAPIError, place_details
from apps.recipes.models import RecipeFavorite, Recipe_list, RecipePhoto
from apps.restaurants.models import PlaceFavorite, PlaceViewHistory, Reservation
from apps.restaurants.local import local_restaurant
from apps.review_models import ContentReview

users = Blueprint("users", __name__, template_folder="templates")
SAMPLE_PLACE_ID = "sample-restaurant"


def _current_user_account():
    email = session.get("email")
    if not email:
        return None, redirect(url_for("auth.login"))

    try:
        account = Account.query.filter_by(email=email).first()
    except SQLAlchemyError:
        current_app.logger.exception("マイページのアカウント取得に失敗しました")
        return None, (
            "マイページ情報を取得できませんでした。時間をおいて再度お試しください。",
            500,
            {"Content-Type": "text/plain; charset=utf-8"},
        )
    if account is None:
        session.clear()
        return None, redirect(url_for("auth.login"))
    if account.account_type != "user":
        return None, redirect(url_for("restaurants.restaurant"))
    return account, None


@users.get("/")
def mypage():
    account, error_response = _current_user_account()
    if error_response:
        return error_response
    try:
        posted_recipes = (
            Recipe_list.query.options(
                selectinload(Recipe_list.photos).load_only(
                    RecipePhoto.id,
                    RecipePhoto.recipe_id,
                    RecipePhoto.step_index,
                )
            )
            .filter_by(account_id=account.id)
            .order_by(Recipe_list.created_at.desc(), Recipe_list.id.desc())
            .all()
        )
        review_count = ContentReview.query.filter_by(
            account_id=account.id,
        ).count()
        posted_reviews = (
            ContentReview.query.options(joinedload(ContentReview.recipe))
            .filter_by(account_id=account.id)
            .order_by(ContentReview.created_at.desc(), ContentReview.id.desc())
            .limit(5)
            .all()
        )
        reservations = (
            Reservation.query.options(joinedload(Reservation.restaurant))
            .filter_by(user_id=account.id)
            .order_by(Reservation.reserved_at.desc(), Reservation.id.desc())
            .all()
        )
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("マイページ情報の取得に失敗しました")
        return (
            "マイページ情報を取得できませんでした。時間をおいて再度お試しください。",
            500,
            {"Content-Type": "text/plain; charset=utf-8"},
        )

    response = make_response(render_template(
        "users/mypage.html",
        account=account,
        posted_recipes=posted_recipes,
        review_count=review_count,
        posted_reviews=posted_reviews,
        reservations=reservations,
    ))
    response.headers["Cache-Control"] = "no-store"
    return response


@users.get("/favorites")
def favorite():
    account, error_response = _current_user_account()
    if error_response:
        return error_response

    try:
        recipe_favorites = (
            RecipeFavorite.query.filter_by(account_id=account.id)
            .order_by(RecipeFavorite.created_at.desc(), RecipeFavorite.id.desc())
            .all()
        )
        place_favorites = (
            PlaceFavorite.query.filter_by(account_id=account.id)
            .order_by(PlaceFavorite.created_at.desc(), PlaceFavorite.id.desc())
            .all()
        )
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("お気に入り情報の取得に失敗しました")
        return (
            "お気に入り情報を取得できませんでした。時間をおいて再度お試しください。",
            500,
            {"Content-Type": "text/plain; charset=utf-8"},
        )

    saved_places, place_lookup_error = _load_places(
        favorite.place_id for favorite in place_favorites
    )
    response = make_response(render_template(
        "users/favorite.html",
        recipe_favorites=recipe_favorites,
        saved_places=[saved_places[favorite.place_id] for favorite in place_favorites],
        place_lookup_error=place_lookup_error,
    ))
    response.headers["Cache-Control"] = "no-store"
    return response


def _load_places(place_ids):
    saved_places = {}
    place_lookup_error = False
    for place_id in dict.fromkeys(place_ids):
        if place_id == SAMPLE_PLACE_ID:
            saved_places[place_id] = {
                "id": place_id,
                "name": "元気ラーメン",
                "address": "東京都〇〇区〇〇町1-2-3",
            }
            continue
        if place_id.startswith("local-store-"):
            try:
                account = local_restaurant(place_id)
            except SQLAlchemyError:
                db.session.rollback()
                current_app.logger.exception("保存した店舗の取得に失敗しました")
                account = None
            if account is None:
                place_lookup_error = True
                saved_places[place_id] = {
                    "id": place_id, "name": "店舗情報を取得できません",
                    "address": "店舗情報を再取得できませんでした。",
                }
            else:
                saved_places[place_id] = {
                    "id": place_id, "name": account.name,
                    "address": account.address or "住所情報なし",
                }
            continue
        try:
            place = place_details(place_id)
        except PlacesAPIError as error:
            current_app.logger.error(
                "保存した店舗のPlaces API取得に失敗しました: HTTP %s, reasons: %s",
                error.status_code,
                ", ".join(error.reasons) or "unknown",
            )
            place_lookup_error = True
            saved_places[place_id] = {
                "id": place_id,
                "name": "店舗情報を取得できません",
                "address": "店舗情報を再取得できませんでした。",
            }
            continue
        except (URLError, TimeoutError, OSError, ValueError, UnicodeError):
            current_app.logger.exception("保存した店舗の取得に失敗しました")
            place_lookup_error = True
            saved_places[place_id] = {
                "id": place_id,
                "name": "店舗情報を取得できません",
                "address": "店舗情報を再取得できませんでした。",
            }
            continue
        saved_places[place_id] = {
            "id": place_id,
            "name": place["name"],
            "address": place["address"] or "住所情報なし",
            "attributions": place.get("attributions", []),
        }
    return saved_places, place_lookup_error


@users.post("/favorites/recipes/<int:recipe_id>")
def toggle_recipe_favorite(recipe_id):
    account, error_response = _current_user_account()
    if error_response:
        return error_response

    recipe = db.get_or_404(Recipe_list, recipe_id)
    action = request.form.get("action")
    if action not in ("add", "remove"):
        return "お気に入り操作が正しくありません。", 400

    favorite = RecipeFavorite.query.filter_by(
        account_id=account.id,
        recipe_id=recipe.id,
    ).first()
    if action == "add" and favorite is None:
        db.session.add(RecipeFavorite(account_id=account.id, recipe_id=recipe.id))
    elif action == "remove" and favorite is not None:
        db.session.delete(favorite)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("レシピのお気に入り保存に失敗しました")
        return (
            "お気に入りを保存できませんでした。時間をおいて再度お試しください。",
            500,
            {"Content-Type": "text/plain; charset=utf-8"},
        )

    if request.form.get("return_to") == "favorites":
        return redirect(url_for("users.favorite"))
    return redirect(url_for("recipes.recipe_detail", recipe_id=recipe.id))


@users.post("/favorites/places/<place_id>")
def toggle_place_favorite(place_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", place_id):
        return "店舗IDが正しくありません。", 400
    account, error_response = _current_user_account()
    if error_response:
        return error_response

    action = request.form.get("action")
    if action not in ("add", "remove"):
        return "お気に入り操作が正しくありません。", 400

    favorite = PlaceFavorite.query.filter_by(
        account_id=account.id,
        place_id=place_id,
    ).first()
    if action == "add" and favorite is None:
        db.session.add(PlaceFavorite(account_id=account.id, place_id=place_id))
    elif action == "remove" and favorite is not None:
        db.session.delete(favorite)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("店舗のお気に入り保存に失敗しました")
        return (
            "お気に入りを保存できませんでした。時間をおいて再度お試しください。",
            500,
            {"Content-Type": "text/plain; charset=utf-8"},
        )

    if request.form.get("return_to") == "favorites":
        return redirect(url_for("users.favorite"))
    if place_id == SAMPLE_PLACE_ID:
        return redirect(url_for("restaurants.restaurant_detail"))
    return redirect(url_for("restaurants.place_detail", place_id=place_id))


@users.get("/history")
def history():
    account, error_response = _current_user_account()
    if error_response:
        return error_response
    try:
        place_history = (
            PlaceViewHistory.query.filter_by(account_id=account.id)
            .order_by(PlaceViewHistory.viewed_at.desc(), PlaceViewHistory.id.desc())
            .all()
        )
        favorite_place_ids = {
            favorite.place_id
            for favorite in PlaceFavorite.query.filter_by(account_id=account.id).all()
        }
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("店舗の閲覧履歴の取得に失敗しました")
        return (
            "閲覧履歴を取得できませんでした。時間をおいて再度お試しください。",
            500,
            {"Content-Type": "text/plain; charset=utf-8"},
        )
    places, place_lookup_error = _load_places(entry.place_id for entry in place_history)
    response = make_response(render_template(
        "users/history.html",
        place_history=place_history,
        places=places,
        favorite_place_ids=favorite_place_ids,
        place_lookup_error=place_lookup_error,
        has_google_places=any(
            entry.place_id != SAMPLE_PLACE_ID and not entry.place_id.startswith("local-store-")
            for entry in place_history
        ),
    ))
    response.headers["Cache-Control"] = "no-store"
    return response


@users.get("/settings")
def setting():
    account, error_response = _current_user_account()
    if error_response:
        return error_response
    response = make_response(render_template(
        "users/setting.html",
        account=account,
    ))
    response.headers["Cache-Control"] = "no-store"
    return response
