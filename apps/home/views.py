import json
import math
import os
from urllib.error import URLError
from urllib.request import Request, urlopen

from flask import Blueprint, current_app, render_template, request

from .places import PlacesAPIError, search_places

home = Blueprint("home", __name__, template_folder="templates")


@home.get("/")
def top():
    """ホーム画面を表示"""
    return render_template("home/top.html")


@home.route("/results", methods=["GET", "POST"])
def results():
    """
    検索結果ページ
    - 気分検索: Ollama AIで料理を提案し、Google Places APIで店舗検索
    - キーワード検索: ユーザーキーワードで店舗検索
    - 入力検証、API エラー処理、距離でのソートを実施
    """
    form = request.form if request.method == "POST" else request.args
    mood = form.get("dishName", "").strip()
    keyword = form.get("keyword", "").strip()
    budget = form.get("budget", "").strip()
    genre = form.get("genre", "").strip()
    recommendation = None
    error = None
    search_error = None
    places_error = None
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
            else:
                if is_mood_search:
                    # 気分検索: Ollama AIで料理提案を取得
                    try:
                        recommendation = suggest_dishes(mood, genre)
                        queries = [dish["name"] + " レストラン" for dish in recommendation]
                    except (URLError, TimeoutError, OSError, ValueError, UnicodeError):
                        current_app.logger.exception("Ollamaによる料理の提案に失敗しました")
                        error = "AIの提案を取得できませんでした。Ollamaとモデルが利用できるか確認して、もう一度お試しください。"
                        status = 503
                else:
                    # キーワード検索: ジャンルを追加してクエリを構築
                    genre_names = {"和": "和食", "洋": "洋食", "中": "中華", "その他": "その他"}
                    queries = [keyword + (" " + genre_names[genre] if genre else "")]

            if queries:
                # Google Places APIで店舗を検索
                seen = set()
                for query in queries:
                    try:
                        found = search_places(query, int(budget) if budget else None, latitude, longitude)
                    except PlacesAPIError as exc:
                        current_app.logger.error("Places API error: HTTP %s, reasons: %s", exc.status_code, ", ".join(exc.reasons) or "unknown")
                        if "API_KEY_INVALID" in exc.reasons:
                            places_error = "Google Maps APIキーが無効です。新しいキーを設定し、アプリを再起動してください。"
                        elif "SERVICE_DISABLED" in exc.reasons:
                            places_error = "Places API (New) が無効です。Google Cloudで有効にしてください。"
                        elif "BILLING_DISABLED" in exc.reasons:
                            places_error = "Google Cloudの課金設定を確認してください。"
                        else:
                            places_error = f"店舗検索でGoogle Places APIエラーが発生しました（HTTP {exc.status_code}）。アプリのログを確認してください。"
                        status = 503
                        break
                    except (URLError, TimeoutError, OSError, ValueError, UnicodeError):
                        current_app.logger.exception("Places APIによる店舗検索に失敗しました")
                        places_error = "一部またはすべての店舗を検索できませんでした。Google Maps APIキーとPlaces APIの設定を確認してください。"
                        status = 503
                        continue
                    for place in found:
                        if place["id"] not in seen:
                            seen.add(place["id"])
                            places.append(place)
                # 距離でソート（距離情報がない場合は最後）
                places.sort(key=lambda place: place["distance"] if place["distance"] is not None else float("inf"))

    return render_template(
        "home/results.html",
        mood=mood,
        keyword=keyword,
        budget=budget,
        genre=genre,
        recommendation=recommendation,
        recommendation_error=error,
        search_error=search_error,
        places=places,
        places_error=places_error,
        is_mood_search=is_mood_search,
        is_places_search=is_places_search,
        places_searched=bool(queries),
    ), status


def suggest_dishes(mood, genre):
    """
    Ollama AIで気分とジャンルに合う料理を提案
    - JSONスキーマで3つの料理を指定形式で取得
    - 入力検証でスキーマ構造と各フィールドの長さをチェック
    """
    payload = json.dumps({
        "model": os.environ.get("OLLAMA_MODEL", "llama3.1"),
        "prompt": (
            "次の気分と料理ジャンルに合う実在する料理を3つ、日本語で短い理由とともに提案してください。"
            "nameは店舗検索に使える簡潔な料理名にしてください。\n"
            f"気分: {mood}\n料理ジャンル: {genre or '指定なし'}"
        ),
        "format": {
            "type": "object",
            "properties": {
                "dishes": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}, "reason": {"type": "string"}},
                        "required": ["name", "reason"],
                    },
                },
            },
            "required": ["dishes"],
        },
        "stream": False,
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
    if not isinstance(result, dict) or not isinstance(result.get("dishes"), list) or len(result["dishes"]) != 3:
        raise ValueError("Ollama returned invalid dishes")
    dishes = []
    for dish in result["dishes"]:
        if not isinstance(dish, dict) or not isinstance(dish.get("name"), str) or not isinstance(dish.get("reason"), str):
            raise ValueError("Ollama returned an invalid dish")
        name, reason = dish["name"].strip(), dish["reason"].strip()
        if not name or len(name) > 80 or not reason or len(reason) > 300:
            raise ValueError("Ollama returned an invalid dish")
        dishes.append({"name": name, "reason": reason})
    return dishes
