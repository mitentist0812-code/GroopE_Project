import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta
from urllib.error import URLError

from flask import (
    Blueprint,
    current_app,
    jsonify,
    make_response,
    render_template,
    request,
    session,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from apps.auth.models import Account
from apps.extensions import db
from apps.home.places import PlacesAPIError, photo_url, place_details

from .models import RestaurantMenu, RestaurantPlaceClaim

restaurants = Blueprint("restaurants", __name__, template_folder="templates")


def _restaurant_account():
    email = session.get("email")
    if not email:
        return None, (jsonify(error="ログインしてください。"), 401)

    try:
        account = Account.query.filter_by(
            email=email,
            account_type="restaurant",
        ).first()
    except SQLAlchemyError:
        current_app.logger.exception("店舗アカウントの確認に失敗しました")
        return None, (jsonify(error="店舗アカウントを確認できませんでした。"), 500)
    if account is None:
        return None, (jsonify(error="店舗アカウントでログインしてください。"), 403)
    return account, None


def _menu_data(menu):
    return {
        "id": menu.id,
        "name": menu.name,
        "price": menu.price,
        "calories": menu.calories,
    }


def _place_claim_code_hash(code):
    key = current_app.config["SECRET_KEY"].encode("utf-8")
    return hmac.new(key, code.encode("ascii"), hashlib.sha256).hexdigest()


@restaurants.get("/")
def restaurant():
    return render_template("restaurants/restaurant.html")


@restaurants.get("/detail")
def restaurant_detail():
    return render_template("restaurants/restaurant_detail.html")


@restaurants.get("/detail/<place_id>")
def place_detail(place_id):
    try:
        place = place_details(place_id)
    except PlacesAPIError as error:
        current_app.logger.error("Places detail API error: HTTP %s, reasons: %s", error.status_code, ", ".join(error.reasons) or "unknown")
        return render_template("restaurants/restaurant_detail.html", place_error="店舗情報を取得できませんでした。Google Places APIの設定を確認してください。", real_place=True), 503
    except (URLError, TimeoutError, OSError, ValueError, UnicodeError):
        current_app.logger.exception("店舗詳細の取得に失敗しました")
        return render_template("restaurants/restaurant_detail.html", place_error="店舗情報を取得できませんでした。時間をおいて再度お試しください。", real_place=True), 503
    photo_error = None
    image_url = None
    if place["photo"]:
        try:
            image_url = photo_url(place["photo"])
        except PlacesAPIError as error:
            current_app.logger.error("Places photo API error: HTTP %s, reasons: %s", error.status_code, ", ".join(error.reasons) or "unknown")
            photo_error = "店舗写真を取得できませんでした。"
        except (URLError, TimeoutError, OSError, ValueError, UnicodeError):
            current_app.logger.exception("店舗写真の取得に失敗しました")
            photo_error = "店舗写真を取得できませんでした。"
    response = make_response(render_template(
        "restaurants/restaurant_detail.html", place=place, real_place=True,
        image_url=image_url, photo_error=photo_error,
    ))
    response.headers["Cache-Control"] = "no-store"
    return response


@restaurants.get("/menu")
def menu_management():
    return render_template("restaurants/menu_management.html")


@restaurants.route("/api/menus", methods=["GET", "POST"])
def menu_items():
    account, error_response = _restaurant_account()
    if error_response:
        return error_response

    if request.method == "GET":
        try:
            menus = RestaurantMenu.query.filter_by(
                restaurant_id=account.id,
            ).order_by(RestaurantMenu.id).all()
        except SQLAlchemyError:
            current_app.logger.exception("店舗メニューの取得に失敗しました")
            return jsonify(error="メニューを取得できませんでした。"), 500
        return jsonify(menus=[_menu_data(menu) for menu in menus])

    payload = request.get_json(silent=True)
    menu_data = payload.get("menus") if isinstance(payload, dict) else None
    if not isinstance(menu_data, list) or not 1 <= len(menu_data) <= 500:
        return jsonify(error="1件以上500件以下のメニューを指定してください。"), 400

    menus = []
    for index, item in enumerate(menu_data, start=1):
        if not isinstance(item, dict):
            return jsonify(error=f"{index}件目のメニュー形式が正しくありません。"), 400

        name = item.get("name")
        price = item.get("price")
        calories = item.get("calories")
        if not isinstance(name, str):
            return jsonify(error=f"{index}件目の料理名を100文字以内で入力してください。"), 400
        name = name.strip()
        if not name or len(name) > 100:
            return jsonify(error=f"{index}件目の料理名を100文字以内で入力してください。"), 400
        if isinstance(price, bool) or not isinstance(price, int):
            return jsonify(error=f"{index}件目の値段は0以上の整数で入力してください。"), 400
        if price < 0 or price > 9007199254740991:
            return jsonify(error=f"{index}件目の値段は0以上の整数で入力してください。"), 400
        if isinstance(calories, bool) or not isinstance(calories, int):
            return jsonify(error=f"{index}件目のカロリーは0以上の整数で入力してください。"), 400
        if calories < 0 or calories > 9007199254740991:
            return jsonify(error=f"{index}件目のカロリーは0以上の整数で入力してください。"), 400

        menus.append(RestaurantMenu(
            restaurant_id=account.id,
            name=name,
            price=price,
            calories=calories,
        ))

    try:
        db.session.add_all(menus)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("店舗メニューの保存に失敗しました")
        return jsonify(error="メニューを保存できませんでした。"), 500
    return jsonify(menus=[_menu_data(menu) for menu in menus]), 201


@restaurants.delete("/api/menus/<int:menu_id>")
def delete_menu_item(menu_id):
    account, error_response = _restaurant_account()
    if error_response:
        return error_response

    menu = RestaurantMenu.query.filter_by(
        id=menu_id,
        restaurant_id=account.id,
    ).first()
    if menu is None:
        return jsonify(error="メニューが見つかりません。"), 404

    try:
        db.session.delete(menu)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("店舗メニューの削除に失敗しました")
        return jsonify(error="メニューを削除できませんでした。"), 500
    return jsonify(success=True)


@restaurants.post("/api/place-claims")
def create_place_claim():
    account, error_response = _restaurant_account()
    if error_response:
        return error_response
    if not current_app.config.get("PLACE_LINK_DEMO_MODE"):
        return jsonify(error="店舗連携のSMS送信は設定されていません。"), 503
    if account.place_id:
        return jsonify(error="この店舗アカウントは既にPlaceと連携済みです。"), 409

    payload = request.get_json(silent=True)
    place_id = payload.get("place_id") if isinstance(payload, dict) else None
    if not isinstance(place_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", place_id):
        return jsonify(error="Place IDが正しくありません。"), 400

    existing_account = Account.query.filter_by(place_id=place_id).first()
    if existing_account:
        return jsonify(error="この店舗は既に別のアカウントと連携済みです。"), 409

    try:
        place = place_details(place_id)
    except PlacesAPIError as error:
        current_app.logger.error(
            "Places claim detail API error: HTTP %s, reasons: %s",
            error.status_code,
            ", ".join(error.reasons) or "unknown",
        )
        return jsonify(error="店舗情報を取得できませんでした。"), 503
    except (URLError, TimeoutError, OSError, ValueError, UnicodeError):
        current_app.logger.exception("店舗連携先の情報取得に失敗しました")
        return jsonify(error="店舗情報を取得できませんでした。時間をおいて再度お試しください。"), 503

    phone = place.get("phone")
    if not isinstance(phone, str) or not phone.strip():
        return jsonify(error="Placesに店舗電話番号が掲載されていません。"), 400
    phone_digits = "".join(character for character in phone if character.isdigit())
    if len(phone_digits) < 4:
        return jsonify(error="店舗電話番号を確認できませんでした。"), 400

    code = f"{secrets.randbelow(1_000_000):06d}"
    claim = RestaurantPlaceClaim.query.filter_by(account_id=account.id).first()
    if claim is None:
        claim = RestaurantPlaceClaim(
            account_id=account.id,
            place_id=place_id,
            code_hash=_place_claim_code_hash(code),
            expires_at=datetime.now() + timedelta(minutes=5),
        )
        db.session.add(claim)
    else:
        claim.place_id = place_id
        claim.code_hash = _place_claim_code_hash(code)
        claim.attempts = 0
        claim.expires_at = datetime.now() + timedelta(minutes=5)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("店舗連携コードの発行に失敗しました")
        return jsonify(error="認証コードを発行できませんでした。"), 500

    return jsonify(
        phone_last4=phone_digits[-4:],
        demo_code=code,
        expires_in=300,
        demo=True,
    ), 201


@restaurants.post("/api/place-claims/verify")
def verify_place_claim():
    account, error_response = _restaurant_account()
    if error_response:
        return error_response
    if not current_app.config.get("PLACE_LINK_DEMO_MODE"):
        return jsonify(error="店舗連携のSMS確認は設定されていません。"), 503

    claim = RestaurantPlaceClaim.query.filter_by(account_id=account.id).first()
    if claim is None:
        return jsonify(error="有効な連携申請がありません。"), 404
    if claim.expires_at <= datetime.now():
        try:
            db.session.delete(claim)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("期限切れ店舗連携コードの削除に失敗しました")
            return jsonify(error="連携コードを確認できませんでした。"), 500
        return jsonify(error="認証コードの有効期限が切れました。もう一度申請してください。"), 410

    payload = request.get_json(silent=True)
    code = payload.get("code") if isinstance(payload, dict) else None
    code_matches = (
        isinstance(code, str)
        and re.fullmatch(r"[0-9]{6}", code) is not None
        and hmac.compare_digest(_place_claim_code_hash(code), claim.code_hash)
    )
    if not code_matches:
        claim.attempts += 1
        locked = claim.attempts >= 5
        if locked:
            db.session.delete(claim)
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("店舗連携コード試行回数の保存に失敗しました")
            return jsonify(error="認証コードを確認できませんでした。"), 500
        if locked:
            return jsonify(error="認証試行回数の上限に達しました。もう一度申請してください。"), 429
        return jsonify(error="認証コードが正しくありません。"), 400

    place_id = claim.place_id
    account.place_id = place_id
    db.session.delete(claim)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="この店舗は既に別のアカウントと連携済みです。"), 409
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("店舗アカウントとPlaceの連携に失敗しました")
        return jsonify(error="店舗を連携できませんでした。"), 500

    session["place_id"] = place_id
    return jsonify(success=True, place_id=place_id)


@restaurants.get("/reservations")
def reservation_management():
    return render_template("restaurants/reservation_management.html")


@restaurants.get("/reservations/new")
def reservation_form():
    return render_template("restaurants/reservation_form.html")
