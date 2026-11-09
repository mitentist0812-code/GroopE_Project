from urllib.error import URLError

from flask import Blueprint, current_app, make_response, render_template

from apps.home.places import PlacesAPIError, photo_url, place_details

restaurants = Blueprint("restaurants", __name__, template_folder="templates")


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


@restaurants.get("/reservations")
def reservation_management():
    return render_template("restaurants/reservation_management.html")


@restaurants.get("/reservations/new")
def reservation_form():
    return render_template("restaurants/reservation_form.html")
