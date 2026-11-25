import base64
import hmac
import json
import math
import os
import re
import secrets
import unicodedata
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Blueprint, current_app, jsonify, render_template, request, session
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import RequestEntityTooLarge

from apps.auth.models import Account
from apps.extensions import db
from .models import CalorieHistory

nutrition = Blueprint("nutrition", __name__, template_folder="templates")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_INGREDIENTS = 20
FOODS = json.loads((Path(__file__).parent / "food_data.json").read_text(encoding="utf-8"))
FOODS_BY_ID = {food["id"]: food for food in FOODS}


def _authentication_error(login_message="ログインしてください。"):
    email = session.get("email")
    account = Account.query.filter_by(email=email).first() if email else None
    if not account:
        return jsonify(error=login_message), 401
    if account.account_type != "user":
        return jsonify(error="店舗アカウントではカロリー計算を利用できません。"), 403
    return None


def _find_foods(query):
    normalized = unicodedata.normalize("NFKC", query).strip().lower()
    return [
        food for food in FOODS
        if normalized in unicodedata.normalize("NFKC", food["name"]).lower()
    ]


def _match_food(name):
    normalized = unicodedata.normalize("NFKC", name).strip().lower()
    if normalized in ("ご飯", "ごはん", "白ご飯"):
        return next(food for food in FOODS if food["id"] == "01088")
    aliases = {"卵": "鶏卵", "鶏肉": "にわとり", "豚肉": "ぶた", "牛肉": "うし", "玉ねぎ": "たまねぎ"}
    normalized = aliases.get(normalized, normalized)
    matches = [
        food for food in _find_foods(normalized)
        if normalized in unicodedata.normalize("NFKC", food["name"]).lower().split()
    ]
    return matches[0] if matches else None


@nutrition.get("/calorie")
def calorie():
    if "calorie_csrf" not in session:
        session["calorie_csrf"] = secrets.token_urlsafe(32)
    return render_template("nutrition/calorie.html", calorie_csrf=session["calorie_csrf"])


@nutrition.get("/foods")
def food_search():
    error = _authentication_error()
    if error:
        return error
    query = unicodedata.normalize("NFKC", request.args.get("q", "")).strip().lower()
    if not query or len(query) > 80:
        return jsonify(error="食品名を80文字以内で入力してください。"), 400
    matches = _find_foods(query)
    return jsonify(foods=matches[:50], truncated=len(matches) > 50)


def _analyze_image(data):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured")
    payload = {
        "contents": [{"parts": [
            {"text": (
                "料理写真から料理名と材料を日本語で推定してください。"
                "食品成分表で材料を選び直すため、各材料の一般的な名前と"
                "実際に食べる量の概算をグラム単位で返してください。"
                "見えない材料や調味料の推定には不確実性があることに注意してください。"
                "料理が写っていない場合はis_foodをfalseにし、材料を空にしてください。"
            )},
            {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(data).decode("ascii")}},
        ]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": {
                "type": "object",
                "properties": {
                    "is_food": {"type": "boolean"},
                    "dish": {"type": "string"},
                    "ingredients": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "grams": {"type": "number"},
                            },
                            "required": ["name", "grams"],
                        },
                    },
                },
                "required": ["is_food", "dish", "ingredients"],
            },
            "temperature": 0,
        },
    }
    api_request = Request(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    with urlopen(api_request, timeout=60) as response:
        result = json.load(response)
    try:
        if not isinstance(result, dict):
            raise ValueError("Invalid Gemini response")
        candidate = result["candidates"][0]
        if not isinstance(candidate, dict) or candidate.get("finishReason") != "STOP":
            raise ValueError("Gemini did not complete the response")
        parts = candidate["content"]["parts"]
        if not isinstance(parts, list) or not all(
            isinstance(part, dict) and isinstance(part.get("text", ""), str) for part in parts
        ):
            raise ValueError("Invalid Gemini response")
        text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
        parsed = json.loads(text)
        if not isinstance(parsed, dict) or not isinstance(parsed.get("is_food"), bool):
            raise ValueError("Invalid Gemini response")
        dish, ingredients = parsed["dish"], parsed["ingredients"]
        if not isinstance(dish, str) or len(dish) > 100 or not isinstance(ingredients, list) or len(ingredients) > MAX_INGREDIENTS:
            raise ValueError("Invalid Gemini response")
        if not parsed["is_food"]:
            return {"is_food": False, "dish": "", "ingredients": []}
        if not dish.strip() or not ingredients:
            raise ValueError("Invalid Gemini response")
        for item in ingredients:
            name, grams = item["name"], item["grams"]
            if (not isinstance(name, str) or not name.strip() or len(name) > 80
                    or isinstance(grams, bool) or not isinstance(grams, (int, float))
                    or not math.isfinite(grams) or not 0 < grams <= 10000):
                raise ValueError("Invalid Gemini ingredient")
        return {"is_food": True, "dish": dish, "ingredients": ingredients}
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Invalid Gemini response") from exc


@nutrition.post("/calorie/analyze")
def analyze_calorie_photo():
    error = _authentication_error("カロリー計算を利用するにはログインしてください。")
    if error:
        return error
    request.max_content_length = MAX_IMAGE_BYTES + 65536
    try:
        token = request.form.get("csrf_token", "")
    except RequestEntityTooLarge:
        return jsonify(error="画像を5MB以下にしてください。"), 413
    expected = session.get("calorie_csrf", "")
    if not expected or not hmac.compare_digest(token, expected):
        return jsonify(error="画面を再読み込みしてからもう一度お試しください。"), 403
    photo = request.files.get("photo")
    if not photo:
        return jsonify(error="料理の写真を選択してください。"), 400
    data = photo.stream.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES or not data.startswith(b"\xff\xd8\xff"):
        return jsonify(error="画像をJPEG形式、5MB以下にしてください。"), 400
    try:
        result = _analyze_image(data)
    except HTTPError as exc:
        current_app.logger.error("Gemini API error: HTTP %s", exc.code)
        return jsonify(error="画像解析に失敗しました。APIの設定や利用枠を確認してください。"), 503
    except (URLError, TimeoutError, OSError, ValueError, UnicodeError):
        current_app.logger.exception("Geminiによる料理画像の解析に失敗しました")
        return jsonify(error="画像解析に失敗しました。設定を確認し、時間をおいて再度お試しください。"), 503
    for item in result["ingredients"]:
        item["food"] = _match_food(item["name"])
    if result["is_food"]:
        result["history_key"] = secrets.token_urlsafe(24)
    return jsonify(result)


@nutrition.route("/calorie/history", defaults={"history_id": None}, methods=["POST"])
@nutrition.route("/calorie/history/<int:history_id>", methods=["PUT"])
def save_calorie_history(history_id):
    request.max_content_length = 65536
    error = _authentication_error("カロリー計算の履歴を保存するにはログインしてください。")
    if error:
        return error
    expected = session.get("calorie_csrf", "")
    token = request.headers.get("X-CSRF-Token", "")
    if not isinstance(expected, str) or not expected or not token.isascii() or not hmac.compare_digest(token, expected):
        return jsonify(error="画面を再読み込みしてからもう一度お試しください。"), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="保存する結果が正しくありません。"), 400
    dish = data.get("dish")
    items = data.get("ingredients")
    save_key = data.get("save_key")
    if (not isinstance(dish, str) or not dish.strip() or len(dish) > 100
            or not isinstance(items, list) or len(items) > MAX_INGREDIENTS
            or not isinstance(save_key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", save_key)):
        return jsonify(error="保存する結果が正しくありません。"), 400

    ingredients = []
    calories = 0
    matched = 0
    for item in items:
        if not isinstance(item, dict):
            return jsonify(error="材料の内容が正しくありません。"), 400
        name, grams, food_id = item.get("name"), item.get("grams"), item.get("food_id")
        if (not isinstance(name, str) or len(name) > 80
                or (grams is not None and (isinstance(grams, bool) or not isinstance(grams, (int, float))
                    or not 0.1 <= grams <= 10000 or not math.isfinite(grams)))
                or (food_id is not None and (not isinstance(food_id, str) or food_id not in FOODS_BY_ID))):
            return jsonify(error="材料の内容が正しくありません。"), 400
        food = FOODS_BY_ID.get(food_id)
        ingredients.append({
            "name": name,
            "grams": grams,
            "food_name": food["name"] if food else None,
            "kcal_per_100g": food["kcal_per_100g"] if food else None,
        })
        if food and grams is not None:
            calories += food["kcal_per_100g"] * grams / 100
            matched += 1

    try:
        account = Account.query.filter_by(email=session["email"]).one()
        if history_id is None:
            entry = CalorieHistory.query.filter_by(account_id=account.id, save_key=save_key).first()
            if entry is None:
                entry = CalorieHistory(account_id=account.id, save_key=save_key)
                db.session.add(entry)
        else:
            entry = CalorieHistory.query.filter_by(id=history_id, account_id=account.id, save_key=save_key).first()
            if entry is None:
                return jsonify(error="履歴が見つかりません。"), 404
        entry.dish = dish
        entry.ingredients = ingredients
        entry.total_calories = math.floor(calories + 0.5) if matched else None
        entry.unmatched_count = len(items) - matched
        db.session.commit()
        return jsonify(id=entry.id)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("カロリー計算履歴の保存に失敗しました")
        return jsonify(error="履歴を保存できませんでした。もう一度お試しください。"), 500
