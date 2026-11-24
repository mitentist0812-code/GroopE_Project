import json
import math
import os
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from urllib.error import URLError
from urllib.request import Request, urlopen

from flask import Blueprint, current_app, jsonify, render_template, request, session
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from apps.auth.models import Account
from apps.extensions import db
from apps.recipes.models import Recipe_list, RecipePhoto
from apps.restaurants.local import local_place_id
from apps.restaurants.models import RestaurantLocation, RestaurantMenu
from apps.review_models import ContentReview
from .places import SEARCH_RADIUS_METERS, PlacesAPIError, distance_meters, search_places, search_place_by_id

home = Blueprint("home", __name__, template_folder="templates")
SEARCH_RADII_KM = ("1", "3", "5", "10")
DEFAULT_SEARCH_RADIUS_KM = str(SEARCH_RADIUS_METERS // 1000)


def _menu_search_key(value):
    return unicodedata.normalize("NFKC", value).casefold().strip()


def _timed_search_places(logger, request_number, request_count, query, budget, latitude, longitude, unlimited=False):
    started_at = time.perf_counter()
    succeeded = False
    try:
        if unlimited:
            result = search_places(query, budget, latitude, longitude, unlimited=True)
        else:
            result = search_places(query, budget, latitude, longitude)
        succeeded = True
        return result
    finally:
        logger.info(
            "search_timing stage=places request=%d/%d duration_s=%.3f outcome=%s",
            request_number,
            request_count,
            time.perf_counter() - started_at,
            "success" if succeeded else "error",
        )


@home.get("/")
def top():
    """ホーム画面を表示"""
    recent_recipes = (
        Recipe_list.query.options(
            selectinload(Recipe_list.photos).load_only(
                RecipePhoto.id, RecipePhoto.recipe_id, RecipePhoto.step_index,
            )
        ).order_by(Recipe_list.created_at.desc(), Recipe_list.id.desc()).limit(3).all()
    )
    return render_template("home/top.html", recent_recipes=recent_recipes)


@home.get("/nearby")
def nearby_places():
    """現在地周辺の飲食店をホーム画面向けに取得"""
    try:
        latitude = float(request.args.get("latitude", ""))
        longitude = float(request.args.get("longitude", ""))
        if not math.isfinite(latitude) or not math.isfinite(longitude) or abs(latitude) > 90 or abs(longitude) > 180:
            raise ValueError("Invalid coordinates")
    except ValueError:
        return jsonify(error="近くのお店を表示するには現在地の取得が必要です。"), 400

    try:
        places = search_places("飲食店", None, latitude, longitude)
    except PlacesAPIError as exc:
        current_app.logger.error(
            "Places API error: HTTP %s, reasons: %s",
            exc.status_code,
            ", ".join(exc.reasons) or "unknown",
        )
        return jsonify(error="近くのお店を取得できませんでした。Google Maps APIの設定を確認してください。"), 503
    except (URLError, TimeoutError, OSError, ValueError, UnicodeError):
        current_app.logger.exception("Places APIによる近くのお店の検索に失敗しました")
        return jsonify(error="近くのお店を取得できませんでした。時間をおいて再度お試しください。"), 503

    places.sort(key=lambda place: place["distance"] if place["distance"] is not None else float("inf"))
    return jsonify(places=places[:3])


@home.route("/recipe-results", methods=["GET", "POST"])
def recipe_results():
    if session.get("account_type") == "restaurant":
        return "店舗アカウントではレシピ検索を利用できません。", 403
    form = request.form if request.method == "POST" else request.args
    keyword = form.get("keyword", "").strip()
    if not keyword or len(keyword) > 200:
        return render_template(
            "home/recipe_results.html", keyword=keyword, recipes=[],
            search_error="キーワードを200文字以内で入力してください。",
        ), 400

    recipes = Recipe_list.query.options(
        selectinload(Recipe_list.photos).load_only(
            RecipePhoto.id, RecipePhoto.recipe_id, RecipePhoto.step_index,
        )
    ).filter(or_(
        Recipe_list.recipe_name.contains(keyword, autoescape=True),
        Recipe_list.ingredients.contains(keyword, autoescape=True),
        Recipe_list.description.contains(keyword, autoescape=True),
    )).order_by(Recipe_list.created_at.desc(), Recipe_list.id.desc()).all()
    return render_template("home/recipe_results.html", keyword=keyword, recipes=recipes)


@home.route("/results", methods=["GET", "POST"])
def results():
    """
    検索結果ページ
    - 気分検索: 入力文とOllama AIによる検索語で店舗検索
    - キーワード検索: ユーザーキーワードで店舗検索
    - 入力検証、API エラー処理、距離でのソートを実施
    """
    request_started_at = time.perf_counter()
    form = request.form if request.method == "POST" else request.args
    mood = form.get("dishName", "").strip()
    keyword = form.get("keyword", "").strip()
    budget = form.get("budget", "").strip()
    genre = form.get("genre", "").strip()
    radius = form.get("radius", DEFAULT_SEARCH_RADIUS_KM)
    if radius == "country":
        radius = "unlimited"
    recommendation = None
    error = None
    search_error = None
    places_error = None
    menu_search_error = None
    menu_location_error = False
    places = []
    is_mood_search = "dishName" in form
    is_free_search = "keyword" in form and not is_mood_search
    is_places_search = is_mood_search or is_free_search
    queries = []
    status = 200
    latitude = None
    longitude = None

    if is_places_search:
        # 入力値の検証
        if is_mood_search and (not mood or len(mood) > 200):
            search_error = "気分を200文字以内で入力してください。"
            status = 400
        elif is_free_search and (not keyword or len(keyword) > 200):
            search_error = "キーワードを200文字以内で入力してください。"
            status = 400
        elif genre not in ("", "和", "洋", "中", "その他"):
            search_error = "料理ジャンルを選択し直してください。"
            status = 400
        elif budget and (not budget.isascii() or not budget.isdecimal() or len(budget) > 9):
            search_error = "予算は0以上の整数で入力してください。"
            status = 400
        elif radius not in (*SEARCH_RADII_KM, "unlimited"):
            search_error = "検索距離を選択し直してください。"
            status = 400
        else:
            # 位置情報の検証
            try:
                latitude = float(form.get("latitude", ""))
                longitude = float(form.get("longitude", ""))
                if not math.isfinite(latitude) or not math.isfinite(longitude) or abs(latitude) > 90 or abs(longitude) > 180:
                    raise ValueError("Invalid coordinates")
            except ValueError:
                places_error = "店舗検索には現在地の取得が必要です。ホーム画面から位置情報を許可して再検索してください。"
                status = 400
            if status == 200:
                genre_names = {"和": "和食", "洋": "洋食", "中": "中華", "その他": "その他"}
                genre_suffix = " " + genre_names[genre] if genre else ""
                if is_mood_search:
                    ai_started_at = time.perf_counter()
                    ai_succeeded = False
                    try:
                        recommendation = suggest_searches(mood, genre)
                        ai_succeeded = True
                        queries.extend(item["name"] for item in recommendation)
                    except (URLError, TimeoutError, OSError, ValueError, UnicodeError):
                        current_app.logger.exception("Ollamaによる検索語の提案に失敗しました")
                        error = "AIの提案を取得できませんでした。入力文のみで店舗を検索します。Ollamaとモデルが利用できるか確認してください。"
                        status = 503
                    finally:
                        current_app.logger.info(
                            "search_timing stage=ollama duration_s=%.3f outcome=%s",
                            time.perf_counter() - ai_started_at,
                            "success" if ai_succeeded else "error",
                        )
                    queries.append(mood + genre_suffix)
                    queries = list(dict.fromkeys(queries))
                else:
                    queries = [keyword + genre_suffix]

            if queries:
                seen = set()
                search_budget = int(budget) if budget else None
                places_started_at = time.perf_counter()
                logger = current_app.logger
                with ThreadPoolExecutor(max_workers=3) as executor:
                    futures = []
                    fatal_error = False
                    for index, query in enumerate(queries):
                        if index == 1:
                            futures = [
                                executor.submit(
                                    _timed_search_places,
                                    logger,
                                    request_number,
                                    len(queries),
                                    remaining,
                                    search_budget,
                                    latitude,
                                    longitude,
                                    radius == "unlimited",
                                )
                                for request_number, remaining in enumerate(queries[1:], start=2)
                            ]
                        try:
                            if index == 0:
                                found = _timed_search_places(
                                    logger, index + 1, len(queries), query,
                                    search_budget, latitude, longitude, radius == "unlimited",
                                )
                            else:
                                found = futures[index - 1].result()
                        except PlacesAPIError as exc:
                            current_app.logger.error("Places API error: HTTP %s, reasons: %s", exc.status_code, ", ".join(exc.reasons) or "unknown")
                            if not fatal_error:
                                if "API_KEY_INVALID" in exc.reasons:
                                    places_error = "Google Maps APIキーが無効です。新しいキーを設定し、アプリを再起動してください。"
                                elif "SERVICE_DISABLED" in exc.reasons:
                                    places_error = "Places API (New) が無効です。Google Cloudで有効にしてください。"
                                elif "BILLING_DISABLED" in exc.reasons:
                                    places_error = "Google Cloudの課金設定を確認してください。"
                                else:
                                    places_error = f"店舗検索でGoogle Places APIエラーが発生しました（HTTP {exc.status_code}）。アプリのログを確認してください。"
                            status = 503
                            fatal_error = True
                            if index == 0:
                                break
                            continue
                        except (URLError, TimeoutError, OSError, ValueError, UnicodeError):
                            current_app.logger.exception("Places APIによる店舗検索に失敗しました")
                            if not fatal_error:
                                places_error = "一部またはすべての店舗を検索できませんでした。Google Maps APIキーとPlaces APIの設定を確認してください。"
                            status = 503
                            continue
                        if fatal_error:
                            continue
                        for place in found:
                            if place["id"] not in seen:
                                seen.add(place["id"])
                                places.append(place)
                # 距離でソート（距離情報がない場合は最後）
                places.sort(key=lambda place: place["distance"] if place["distance"] is not None else float("inf"))
                logger.info(
                    "search_timing stage=places_batch requests=%d duration_s=%.3f",
                    len(queries),
                    time.perf_counter() - places_started_at,
                )

    if queries:
        try:
            registered_restaurants = Account.query.filter(
                Account.account_type == "restaurant",
                Account.place_id.isnot(None),
                Account.place_id != "",
            ).all()
            registered_place_ids = {restaurant.place_id for restaurant in registered_restaurants}
            review_rows = (
                db.session.query(
                    ContentReview.place_id,
                    func.avg(ContentReview.rating),
                    func.count(ContentReview.id),
                )
                .filter(ContentReview.place_id.isnot(None))
                .group_by(ContentReview.place_id)
                .all()
            )
            ratings = {
                place_id: (average, count) for place_id, average, count in review_rows
            }
            menu_rows = (
                db.session.query(Account.place_id, RestaurantMenu.name, RestaurantMenu.price)
                .join(RestaurantMenu, RestaurantMenu.restaurant_id == Account.id)
                .filter(
                    Account.account_type == "restaurant",
                    Account.place_id.isnot(None),
                    Account.place_id != "",
                )
                .all()
            )
            local_menu_rows = (
                db.session.query(Account, RestaurantLocation, RestaurantMenu)
                .join(RestaurantLocation, RestaurantLocation.restaurant_id == Account.id)
                .outerjoin(RestaurantMenu, RestaurantMenu.restaurant_id == Account.id)
                .filter(
                    Account.account_type == "restaurant",
                    or_(Account.place_id.is_(None), Account.place_id == ""),
                )
                .all()
            )
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("店舗メニューの検索に失敗しました")
            menu_search_error = "店舗メニューを検索できませんでした。時間をおいて再度お試しください。"
            status = 503
        else:
            term = _menu_search_key(mood if is_mood_search else keyword)
            matching_menus = {}
            for place_id, name, price in menu_rows:
                menu_name = _menu_search_key(name)
                if (
                    term and menu_name
                    and (term in menu_name or menu_name in term)
                    and (not budget or price <= int(budget))
                ):
                    matching_menus.setdefault(place_id, []).append({"name": name, "price": price})

            places_by_id = {place["id"]: place for place in places}
            local_places = {}
            for account, location, menu in local_menu_rows:
                store_name = _menu_search_key(account.name)
                name_match = bool(term and store_name and (term in store_name or store_name in term))
                menu_name = _menu_search_key(menu.name) if menu else ""
                menu_match = bool(term and menu_name and (term in menu_name or menu_name in term))
                if not name_match and not menu_match:
                    continue
                if budget and (menu is None or menu.price > int(budget)):
                    continue
                place_id = local_place_id(account.id)
                distance = distance_meters(latitude, longitude, {
                    "latitude": location.latitude, "longitude": location.longitude,
                })
                if distance is None or (radius != "unlimited" and distance > SEARCH_RADIUS_METERS):
                    continue
                if place_id not in local_places:
                    local_places[place_id] = {
                        "id": place_id, "name": account.name, "address": account.address or "",
                        "distance_exact": distance, "distance": round(distance),
                        "rating": None, "price": "不明", "url": "", "attributions": [],
                        "account_registered": True, "local_restaurant": True, "matching_menus": [],
                    }
                if menu_match:
                    local_places[place_id]["matching_menus"].append({"name": menu.name, "price": menu.price})
            places.extend(local_places.values())
            for place in places:
                if not place.get("local_restaurant"):
                    place["account_registered"] = place["id"] in registered_place_ids
                    place["matching_menus"] = matching_menus.get(place["id"], [])
                if place["id"] in ratings:
                    place["system_rating"], place["system_rating_count"] = ratings[place["id"]]

            missing_place_ids = [
                place_id for place_id in matching_menus if place_id not in places_by_id
            ]
            if missing_place_ids:
                with ThreadPoolExecutor(max_workers=3) as executor:
                    futures = {
                        place_id: executor.submit(search_place_by_id, place_id, latitude, longitude)
                        for place_id in missing_place_ids
                    }
                    for place_id, future in futures.items():
                        try:
                            place = future.result()
                        except PlacesAPIError as exc:
                            current_app.logger.error(
                                "店舗メニューの店舗取得に失敗しました: HTTP %s, reasons: %s",
                                exc.status_code,
                                ", ".join(exc.reasons) or "unknown",
                            )
                            menu_search_error = "一部の店舗メニューの店舗情報を取得できませんでした。"
                            status = 503
                            continue
                        except (URLError, TimeoutError, OSError, ValueError, UnicodeError):
                            current_app.logger.exception("店舗メニューの店舗取得に失敗しました")
                            menu_search_error = "一部の店舗メニューの店舗情報を取得できませんでした。"
                            status = 503
                            continue
                        distance = place["distance"]
                        if distance is None:
                            current_app.logger.warning("店舗メニューの店舗に位置情報がありません")
                            menu_location_error = True
                            continue
                        if radius != "unlimited" and distance > SEARCH_RADIUS_METERS:
                            continue
                        place["distance_exact"] = distance
                        place["distance"] = round(distance)
                        place["account_registered"] = True
                        place["matching_menus"] = matching_menus[place_id]
                        if place_id in ratings:
                            place["system_rating"], place["system_rating_count"] = ratings[place_id]
                        places.append(place)
            places.sort(key=lambda place: place["distance"] if place["distance"] is not None else float("inf"))

    response = render_template(
        "home/results.html",
        mood=mood,
        keyword=keyword,
        budget=budget,
        genre=genre,
        search_radii_km=SEARCH_RADII_KM,
        default_search_radius_km=DEFAULT_SEARCH_RADIUS_KM,
        recommendation=recommendation,
        recommendation_error=error,
        search_error=search_error,
        places=places,
        places_error=places_error,
        menu_search_error=menu_search_error,
        menu_location_error=menu_location_error,
        radius=radius,
        latitude=latitude,
        longitude=longitude,
        has_google_places=any(not place.get("local_restaurant") for place in places),
        is_mood_search=is_mood_search,
        is_places_search=is_places_search,
        places_searched=bool(queries),
    )
    if is_places_search:
        current_app.logger.info(
            "search_timing stage=total duration_s=%.3f status=%d",
            time.perf_counter() - request_started_at,
            status,
        )
    return response, status


def suggest_searches(mood, genre):
    """
    Ollama AIで気分とジャンルに合う店舗検索語を提案
    - JSONスキーマで3つの検索語を指定形式で取得
    - 入力検証でスキーマ構造と各フィールドの長さをチェック
    """
    payload = json.dumps({
        "model": os.environ.get("OLLAMA_MODEL", "llama3.1"),
        "prompt": (
            "入力文から飲食店の検索語を3つ生成してください。"
            "店舗の種類が指定されているときは、全ての検索語にその店舗の種類を含めてください。"
            "例：ファミレス→「ファミリーレストラン」、「ファミレス」、「洋食 ファミリーレストラン」。"
            "例：居酒屋→「居酒屋」、「和食 居酒屋」、「焼き鳥 居酒屋」。"
            "気分だけのときは、その言葉の意味に合う料理と店舗を提案してください。"
            "「がっつり」は量が多く食べ応えがあることを意味します。"
            "例えば焼肉、ステーキ、丼もの、定食などを提案してください。"
            "「がっつり」だけでは辛さを求めているとは判断せず、激辛や辛い料理を提案しないでください。"
            "入力に辛い料理を希望すると明記されている場合は、辛さと食べ応えの両方を反映してください。"
            "例：がっつり辛い料理→「麻婆豆腐 定食」、「辛いラーメン」、「スパイシーカレー」。"
            "入力にない好みを勝手に決めつけないでください。"
            "検索語の名前と理由をJSONで返してください。"
            f"\n入力：{mood}\n料理ジャンル：{genre or '指定なし'}"
        ),
        "format": {
            "type": "object",
            "properties": {
                "suggestions": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "minLength": 1},
                            "reason": {"type": "string", "minLength": 1},
                        },
                        "required": ["name", "reason"],
                    },
                },
            },
            "required": ["suggestions"],
        },
        "stream": False,
        "options": {"temperature": 0},
    }).encode("utf-8")
    api_request = Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(api_request, timeout=120) as response:
        data = json.load(response)
    if not isinstance(data, dict) or not isinstance(data.get("response"), str):
        raise ValueError("Ollama returned an invalid response")
    result = json.loads(data["response"])
    if not isinstance(result, dict) or not isinstance(result.get("suggestions"), list) or len(result["suggestions"]) != 3:
        raise ValueError("Ollama returned invalid suggestions")
    suggestions = []
    for item in result["suggestions"]:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not isinstance(item.get("reason"), str):
            raise ValueError("Ollama returned an invalid suggestion")
        name, reason = item["name"].strip(), item["reason"].strip()
        if not name or len(name) > 80 or not reason or len(reason) > 300:
            raise ValueError("Ollama returned an invalid suggestion")
        suggestions.append({"name": name, "reason": reason})
    return suggestions
