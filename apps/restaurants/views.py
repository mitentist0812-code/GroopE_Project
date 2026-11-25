import hashlib
import hmac
import math
import re
import secrets
from datetime import datetime, timedelta
from urllib.error import URLError

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from apps.allergens import (
    AllergenModelUnavailable,
    USER_ALLERGEN_MODEL_LABELS,
    UNSUPPORTED_USER_ALLERGENS,
    analyze_allergens,
    matching_user_allergens,
)
from apps.auth.models import Account, AccountPreference
from apps.extensions import db
from apps.home.places import PlacesAPIError, photo_url, place_details
from apps.review_utils import current_reviewer, load_reviews, save_review_form

from .local import local_restaurant
from .models import PlaceFavorite, PlaceViewHistory, Reservation, RestaurantLocation, RestaurantMenu, RestaurantPlaceClaim

restaurants = Blueprint("restaurants", __name__, template_folder="templates")
SAMPLE_RESTAURANT_ID = "sample-restaurant"


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


def _record_place_view(reviewer, place_id):
    if reviewer is None:
        return False
    try:
        db.session.add(PlaceViewHistory(account_id=reviewer.id, place_id=place_id))
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("店舗の閲覧履歴の保存に失敗しました")
        return True
    return False


def _reviewer_allergies(reviewer):
    if reviewer is None:
        return [], False
    try:
        preferences = AccountPreference.query.filter_by(
            account_id=reviewer.id,
        ).first()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("利用者のアレルギー設定を取得できませんでした")
        return [], True

    allergies = preferences.allergies if preferences else []
    return [
        allergy for allergy in allergies
        if allergy in USER_ALLERGEN_MODEL_LABELS
    ], False


@restaurants.get("/")
def restaurant():
    return render_template("restaurants/restaurant.html")


@restaurants.get("/detail")
def restaurant_detail():
    reviewer = current_reviewer()
    user_allergies, user_settings_error = _reviewer_allergies(reviewer)
    is_favorite = bool(
        reviewer
        and PlaceFavorite.query.filter_by(
            account_id=reviewer.id,
            place_id=SAMPLE_RESTAURANT_ID,
        ).first()
    )
    reviews, average_rating, own_review = load_reviews(
        place_id=SAMPLE_RESTAURANT_ID,
        reviewer=reviewer,
        sort=request.args.get("sort", "newest"),
    )
    history_error = _record_place_view(reviewer, SAMPLE_RESTAURANT_ID)
    response = make_response(render_template(
        "restaurants/restaurant_detail.html",
        reviews=reviews,
        average_rating=average_rating,
        own_review=own_review,
        reviewer=reviewer,
        is_favorite=is_favorite,
        history_error=history_error,
        review_sort=request.args.get("sort", "newest"),
        user_allergies=user_allergies,
        user_settings_error=user_settings_error,
    ))
    response.headers["Cache-Control"] = "no-store"
    return response


@restaurants.post("/detail/reviews")
def submit_sample_restaurant_review():
    return _submit_restaurant_review(
        SAMPLE_RESTAURANT_ID,
        "restaurants.restaurant_detail",
    )


@restaurants.get("/detail/<place_id>")
def place_detail(place_id):
    local_account = None
    if place_id.startswith("local-store-"):
        try:
            local_account = local_restaurant(place_id)
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("店舗詳細の取得に失敗しました")
            return "店舗情報を取得できませんでした。", 500
        if local_account is None:
            return "店舗が見つかりません。", 404
        place = {
            "id": place_id, "name": local_account.name, "address": local_account.address,
            "rating": None, "price": "不明", "phone": "",
            "hours": [], "website": "", "url": "", "attributions": [], "photo": None,
        }
    else:
        try:
            place = place_details(place_id)
        except PlacesAPIError as error:
            current_app.logger.error(
                "Places detail API error: HTTP %s, reasons: %s",
                error.status_code,
                ", ".join(error.reasons) or "unknown",
            )
            return render_template(
                "restaurants/restaurant_detail.html",
                place_error="店舗情報を取得できませんでした。Google Places APIの設定を確認してください。",
                real_place=True,
            ), 503
        except (URLError, TimeoutError, OSError, ValueError, UnicodeError):
            current_app.logger.exception("店舗詳細の取得に失敗しました")
            return render_template(
                "restaurants/restaurant_detail.html",
                place_error="店舗情報を取得できませんでした。時間をおいて再度お試しください。",
                real_place=True,
            ), 503
    photo_error = None
    image_url = None
    if place["photo"]:
        try:
            image_url = photo_url(place["photo"])
        except PlacesAPIError as error:
            current_app.logger.error(
                "Places photo API error: HTTP %s, reasons: %s",
                error.status_code,
                ", ".join(error.reasons) or "unknown",
            )
            photo_error = "店舗写真を取得できませんでした。"
        except (URLError, TimeoutError, OSError, ValueError, UnicodeError):
            current_app.logger.exception("店舗写真の取得に失敗しました")
            photo_error = "店舗写真を取得できませんでした。"

    reviewer = current_reviewer()
    user_allergies, user_settings_error = _reviewer_allergies(reviewer)
    unsupported_user_allergies = [
        allergy for allergy in user_allergies
        if allergy in UNSUPPORTED_USER_ALLERGENS
    ]
    store_menu_matches = []
    store_menus_available = False
    store_menu_error = False
    allergen_model_error = False
    restaurant_account = None
    try:
        restaurant_account = local_account or Account.query.filter_by(
            place_id=place_id, account_type="restaurant",
        ).first()
        store_menus = (
            RestaurantMenu.query.filter_by(
                restaurant_id=restaurant_account.id,
            ).order_by(RestaurantMenu.id).all()
            if restaurant_account else []
        )
        store_menus_available = bool(store_menus)
        if store_menus:
            predictions = analyze_allergens([menu.name for menu in store_menus])
            store_menu_matches = [
                {
                    "name": menu.name,
                    "possible_allergens": possible_allergens,
                    "matching_user_allergens": matching_user_allergens(
                        user_allergies,
                        possible_allergens,
                    ),
                }
                for menu, possible_allergens in zip(store_menus, predictions)
                if possible_allergens
            ]
    except SQLAlchemyError:
        current_app.logger.exception(
            "店舗メニューのアレルゲン情報を取得できませんでした"
        )
        db.session.rollback()
        store_menu_error = True
    except AllergenModelUnavailable:
        current_app.logger.exception("店舗メニューのアレルゲン候補判定に失敗しました")
        allergen_model_error = True

    is_favorite = bool(
        reviewer
        and PlaceFavorite.query.filter_by(
            account_id=reviewer.id,
            place_id=place_id,
        ).first()
    )
    reviews, average_rating, own_review = load_reviews(
        place_id=place_id,
        reviewer=reviewer,
        sort=request.args.get("sort", "newest"),
    )
    history_error = _record_place_view(reviewer, place_id)
    response = make_response(render_template(
        "restaurants/restaurant_detail.html", place=place, real_place=True,
        image_url=image_url, photo_error=photo_error,
        reviews=reviews,
        average_rating=average_rating,
        own_review=own_review,
        reviewer=reviewer,
        is_favorite=is_favorite,
        history_error=history_error,
        review_sort=request.args.get("sort", "newest"),
        place_id=place_id,
        store_menu_matches=store_menu_matches,
        store_menus_available=store_menus_available,
        store_menu_error=store_menu_error,
        allergen_model_error=allergen_model_error,
        user_allergies=user_allergies,
        user_settings_error=user_settings_error,
        unsupported_user_allergies=unsupported_user_allergies,
        local_place=local_account is not None,
        reservation_available=(
            restaurant_account is not None and not store_menu_error
            and (local_account is None or current_app.config.get("PLACE_LINK_DEMO_MODE"))
        ),
    ))
    response.headers["Cache-Control"] = "no-store"
    return response


@restaurants.post("/detail/<place_id>/reviews")
def submit_restaurant_review(place_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", place_id):
        return jsonify(error="Place IDが正しくありません。"), 400
    return _submit_restaurant_review(
        place_id,
        "restaurants.place_detail",
        place_id=place_id,
    )


def _submit_restaurant_review(target_place_id, endpoint, **endpoint_values):
    email = session.get("email")
    account = Account.query.filter_by(email=email).first() if email else None
    error = save_review_form(
        account,
        request.form,
        place_id=target_place_id,
    )
    if error:
        flash(error, "error")
    else:
        flash("レビューを投稿しました。", "success")
    return redirect(url_for(endpoint, **endpoint_values))


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
    account, error = _restaurant_account()
    if error:
        return error
    try:
        reservations = (
            Reservation.query.filter_by(restaurant_id=account.id)
            .order_by(Reservation.reserved_at.desc(), Reservation.id.desc())
            .all()
        )
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("予約一覧の取得に失敗しました")
        return "予約一覧を取得できませんでした。", 500
    response = make_response(render_template(
        "restaurants/reservation_management.html",
        reservations=reservations,
        csrf_token=_reservation_csrf_token(),
        now=datetime.now(),
    ))
    response.headers["Cache-Control"] = "no-store"
    return response


def _reservation_csrf_token():
    if "reservation_csrf" not in session:
        session["reservation_csrf"] = secrets.token_urlsafe(32)
    return session["reservation_csrf"]


def _valid_reservation_csrf():
    token = request.form.get("csrf_token", "")
    expected = session.get("reservation_csrf")
    return (
        isinstance(expected, str)
        and re.fullmatch(r"[A-Za-z0-9_-]+", token) is not None
        and hmac.compare_digest(token, expected)
    )


@restaurants.route("/location", methods=["GET", "POST"])
def restaurant_location():
    account, error_response = _restaurant_account()
    if error_response:
        return error_response
    try:
        location = db.session.get(RestaurantLocation, account.id)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("店舗位置の取得に失敗しました")
        return "店舗位置を取得できませんでした。", 500
    error = None
    status = 200
    if request.method == "POST":
        if not _valid_reservation_csrf():
            return "フォームの有効期限が切れました。もう一度お試しください。", 400
        try:
            latitude = float(request.form.get("latitude", ""))
            longitude = float(request.form.get("longitude", ""))
            if not math.isfinite(latitude) or not math.isfinite(longitude) or abs(latitude) > 90 or abs(longitude) > 180:
                raise ValueError("Invalid coordinates")
        except ValueError:
            error = "緯度は-90〜90、経度は-180〜180の数値で入力してください。"
            status = 400
        else:
            if location is None:
                location = RestaurantLocation(restaurant_id=account.id)
                db.session.add(location)
            location.latitude = latitude
            location.longitude = longitude
            try:
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                current_app.logger.exception("店舗位置の保存に失敗しました")
                return "店舗位置を保存できませんでした。", 500
            flash("店舗の位置を保存しました。", "success")
            return redirect(url_for("restaurants.restaurant_location"))
    response = make_response(render_template(
        "restaurants/restaurant_location.html", location=location,
        csrf_token=_reservation_csrf_token(), error=error,
    ), status)
    response.headers["Cache-Control"] = "no-store"
    return response


@restaurants.route("/reservations/<place_id>/new", methods=["GET", "POST"])
def reservation_form(place_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", place_id):
        return "店舗IDが正しくありません。", 400
    email = session.get("email")
    if not email:
        return redirect(url_for("auth.login"))
    try:
        user = Account.query.filter_by(email=email, account_type="user").first()
        if place_id.startswith("local-store-"):
            restaurant_account = local_restaurant(place_id) if current_app.config.get("PLACE_LINK_DEMO_MODE") else None
        else:
            restaurant_account = Account.query.filter_by(
                place_id=place_id, account_type="restaurant",
            ).first()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("予約のアカウント確認に失敗しました")
        return "予約情報を確認できませんでした。", 500
    if user is None:
        return "予約できるのは一般ユーザーのみです。", 403
    if restaurant_account is None:
        return "この店舗は予約に対応していません。", 404

    error = None
    status_code = 200
    submission_key = secrets.token_hex(32)
    if request.method == "POST":
        if not _valid_reservation_csrf():
            return "予約フォームの有効期限が切れました。もう一度お試しください。", 400
        submission_key = request.form.get("submission_key", "")
        name = request.form.get("name", "").strip()
        guests = request.form.get("guests", "")
        date_text = request.form.get("datetime", "")
        if not re.fullmatch(r"[0-9a-f]{64}", submission_key):
            return "予約フォームが正しくありません。", 400
        try:
            existing = Reservation.query.filter_by(submission_key=submission_key).first()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("予約申請の確認に失敗しました")
            return "予約申請を確認できませんでした。", 500
        if existing:
            if existing.user_id != user.id or existing.restaurant_id != restaurant_account.id:
                return "予約フォームが正しくありません。", 400
            return redirect(url_for("users.mypage"))
        if not name or len(name) > 100 or not re.fullmatch(r"[\u30A0-\u30FF\u31F0-\u31FF\u3000\s]+", name):
            error = "お名前はカタカナで100文字以内にしてください。"
        elif not re.fullmatch(r"(?:[1-9]|1[0-9]|20)", guests):
            error = "人数は1～20名で入力してください。"
        elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", date_text):
            error = "予約日時を正しく入力してください。"
        else:
            try:
                reserved_at = datetime.strptime(date_text, "%Y-%m-%dT%H:%M")
            except ValueError:
                error = "予約日時を正しく入力してください。"
            else:
                if reserved_at <= datetime.now():
                    error = "現在より後の予約日時を入力してください。"
        if error:
            status_code = 400
        else:
            db.session.add(Reservation(
                user_id=user.id,
                restaurant_id=restaurant_account.id,
                name=name,
                guests=int(guests),
                reserved_at=reserved_at,
                submission_key=submission_key,
                is_demo=bool(current_app.config.get("PLACE_LINK_DEMO_MODE")),
            ))
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                existing = Reservation.query.filter_by(submission_key=submission_key).first()
                if existing and existing.user_id == user.id and existing.restaurant_id == restaurant_account.id:
                    return redirect(url_for("users.mypage"))
                current_app.logger.exception("予約申請の保存に失敗しました")
                return "予約申請を保存できませんでした。", 500
            except SQLAlchemyError:
                db.session.rollback()
                current_app.logger.exception("予約申請の保存に失敗しました")
                return "予約申請を保存できませんでした。", 500
            flash("予約を申請しました。店舗の承認後に確定します。", "success")
            return redirect(url_for("users.mypage"))

    response = make_response(render_template(
        "restaurants/reservation_form.html",
        restaurant_account=restaurant_account,
        place_id=place_id,
        csrf_token=_reservation_csrf_token(),
        submission_key=submission_key,
        error=error,
        local_place=place_id.startswith("local-store-"),
    ), status_code)
    response.headers["Cache-Control"] = "no-store"
    return response


@restaurants.post("/reservations/<int:reservation_id>/status")
def update_reservation_status(reservation_id):
    account, error = _restaurant_account()
    if error:
        return error
    if not _valid_reservation_csrf():
        return "予約操作の有効期限が切れました。もう一度お試しください。", 400
    action = request.form.get("action")
    if action not in ("confirm", "cancel"):
        return "予約操作が正しくありません。", 400
    allowed = ("pending",) if action == "confirm" else ("pending", "confirmed")
    new_status = "confirmed" if action == "confirm" else "cancelled"
    try:
        statement = db.update(Reservation).where(
            Reservation.id == reservation_id,
            Reservation.restaurant_id == account.id,
            Reservation.status.in_(allowed),
        )
        if action == "confirm":
            statement = statement.where(Reservation.reserved_at > datetime.now())
        result = db.session.execute(statement.values(status=new_status))
        if result.rowcount != 1:
            db.session.rollback()
            return "予約が見つからないか、既に変更されたか、予約日時が過ぎています。", 404
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("予約状態の更新に失敗しました")
        return "予約状態を更新できませんでした。", 500
    flash("予約を承認しました。" if action == "confirm" else "予約をキャンセルしました。", "success")
    return redirect(url_for("restaurants.reservation_management"))
