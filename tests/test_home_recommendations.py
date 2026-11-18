import io
import json
import math
import re
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from apps import create_app
from apps.extensions import db
from apps.home.places import PlacesAPIError, budget_price_levels, photo_url, place_details, search_places
from apps.recipes.models import Recipe_list


SUGGESTIONS = [
    {"name": "うどん レストラン", "reason": "さっぱり"},
    {"name": "そば レストラン", "reason": "軽い"},
    {"name": "寿司 レストラン", "reason": "食べやすい"},
]
FORM = {
    "dishName": "さっぱり",
    "genre": "和",
    "budget": "12345",
    "latitude": "35.68",
    "longitude": "139.76",
}


def json_response(data):
    return io.BytesIO(json.dumps(data, ensure_ascii=False).encode("utf-8"))


class HomeRecommendationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    @patch("apps.home.views.search_places")
    def test_home_loads_nearby_places_from_the_browser_location(self, search):
        search.return_value = [
            {"id": "farther", "name": "少し遠い店", "distance": 900, "rating": 4.2, "url": "", "address": "住所"},
            {"id": "nearest", "name": "近い店", "distance": 150, "rating": 4.5, "url": "", "address": "住所"},
            {"id": "middle", "name": "中間の店", "distance": 500, "rating": None, "url": "", "address": "住所"},
            {"id": "last", "name": "4番目の店", "distance": 1000, "rating": 4.0, "url": "", "address": "住所"},
        ]

        home_response = self.client.get("/")
        self.assertEqual(home_response.status_code, 200)
        self.assertIn('id="nearby-places"', home_response.get_data(as_text=True))
        search.assert_not_called()

        response = self.client.get("/nearby?latitude=35.68&longitude=139.76")
        self.assertEqual(response.status_code, 200)
        search.assert_called_once_with("飲食店", None, 35.68, 139.76)
        self.assertEqual([place["id"] for place in response.json["places"]], ["nearest", "middle", "farther"])

    @patch("apps.home.views.search_places")
    def test_nearby_search_rejects_invalid_coordinates(self, search):
        response = self.client.get("/nearby?latitude=NaN&longitude=139.76")
        self.assertEqual(response.status_code, 400)
        self.assertIn("現在地", response.json["error"])
        search.assert_not_called()

    @patch("apps.home.views.search_places", return_value=[])
    @patch("apps.home.views.urlopen")
    def test_sends_mood_and_genre_but_not_budget_or_location_to_ollama(self, urlopen, places):
        urlopen.return_value.__enter__.return_value = json_response({"response": json.dumps({"suggestions": SUGGESTIONS})})
        response = self.client.post("/results", data=FORM)
        self.assertEqual(response.status_code, 200)
        self.assertIn("うどん", response.get_data(as_text=True))
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertIn("さっぱり", payload["prompt"])
        self.assertIn("料理ジャンル：和", payload["prompt"])
        self.assertNotIn("12345", payload["prompt"])
        self.assertNotIn("35.68", payload["prompt"])
        self.assertEqual(places.call_args_list[0].args[0], "うどん レストラン")
        self.assertCountEqual([call.args[0] for call in places.call_args_list[1:]], ["そば レストラン", "寿司 レストラン", "さっぱり 和食"])
        self.assertEqual(places.call_args.args[1:], (12345, 35.68, 139.76))

    @patch("apps.home.views.search_places", return_value=[])
    @patch("apps.home.views.urlopen")
    def test_prompt_distinguishes_hearty_and_explicitly_spicy_requests(self, urlopen, places):
        for mood in ("がっつり", "がっつり辛い料理"):
            with self.subTest(mood=mood):
                urlopen.return_value.__enter__.return_value = json_response({"response": json.dumps({"suggestions": SUGGESTIONS})})
                response = self.client.post("/results", data={**FORM, "dishName": mood})
                self.assertEqual(response.status_code, 200)
                prompt = json.loads(urlopen.call_args.args[0].data)["prompt"]
                self.assertIn("入力：" + mood, prompt)
                self.assertIn("量が多く食べ応え", prompt)
                self.assertIn("「がっつり」だけでは辛さを求めているとは判断せず", prompt)
                self.assertIn("辛さと食べ応えの両方を反映", prompt)

    @patch("apps.home.views.search_places", return_value=[])
    @patch("apps.home.views.urlopen")
    def test_ai_store_types_are_used_as_search_terms_without_a_forced_suffix(self, urlopen, places):
        for mood, names in (
            ("ファミレス", ["ファミリーレストラン", "洋食 ファミリーレストラン", "ファミレス"]),
            ("居酒屋", ["居酒屋", "和食 居酒屋", "焼き鳥 居酒屋"]),
        ):
            with self.subTest(mood=mood):
                places.reset_mock()
                suggestions = [{"name": name, "reason": "希望に合う"} for name in names]
                urlopen.return_value.__enter__.return_value = json_response({
                    "response": json.dumps({"suggestions": suggestions}, ensure_ascii=False),
                })
                response = self.client.post("/results", data={**FORM, "dishName": mood})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(places.call_args_list[0].args[0], names[0])
                self.assertCountEqual([call.args[0] for call in places.call_args_list], names + [mood + " 和食"])
                for name in names:
                    self.assertIn(name, response.get_data(as_text=True))
                payload = json.loads(urlopen.call_args.args[0].data)
                self.assertIn("店舗の種類", payload["prompt"])
                self.assertIn("全ての検索語", payload["prompt"])

    @patch("apps.home.views.search_places", return_value=[])
    @patch("apps.home.views.suggest_searches", return_value=SUGGESTIONS)
    def test_mood_search_uses_input_and_ai_suggestions(self, suggest, search):
        response = self.client.post("/results", data=FORM)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(search.call_args_list[0].args[0], "うどん レストラン")
        self.assertCountEqual([call.args[0] for call in search.call_args_list[1:]],
                              ["そば レストラン", "寿司 レストラン", "さっぱり 和食"])
        text = response.get_data(as_text=True)
        self.assertIn("入力文とAIの検索提案による検索結果", text)

    @patch("apps.home.views.search_places", return_value=[])
    @patch("apps.home.views.suggest_searches", return_value=SUGGESTIONS)
    def test_duplicate_input_and_ai_search_terms_are_only_searched_once(self, suggest, search):
        response = self.client.post("/results", data={**FORM, "dishName": "うどん レストラン", "genre": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(search.call_count, 3)
        self.assertEqual(sum(call.args[0] == "うどん レストラン" for call in search.call_args_list), 1)

    @patch("apps.home.views.search_places")
    @patch("apps.home.views.suggest_searches", return_value=SUGGESTIONS)
    def test_input_search_results_are_included_with_ai_results(self, suggest, search):
        def find_places(query, *args):
            name = "入力から見つかった店" if query == "さっぱり 和食" else "AIから見つかった店"
            return [{"id": name, "name": name, "address": "", "distance": 10,
                     "distance_exact": 10, "rating": None, "price": "不明", "url": "", "attributions": []}]

        search.side_effect = find_places
        response = self.client.post("/results", data=FORM)
        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("入力から見つかった店", text)
        self.assertIn("AIから見つかった店", text)
        self.assertEqual(text.count("<h3>AIから見つかった店</h3>"), 1)

    @patch("apps.home.views.search_places", return_value=[])
    @patch("apps.home.views.suggest_searches", return_value=SUGGESTIONS)
    def test_ai_suggestions_start_collapsed(self, suggest, search):
        response = self.client.post("/results", data=FORM)
        text = response.get_data(as_text=True)
        self.assertRegex(text, r'(?s)<details class="ai-recommendation">\s*<summary>.*?AIの提案を見る.*?</summary>.*?うどん レストラン.*?</details>')
        self.assertEqual(text.count("うどん レストラン"), 1)

    @patch("apps.home.views.search_places")
    @patch("apps.home.views.suggest_searches", return_value=SUGGESTIONS)
    def test_remaining_searches_run_concurrently(self, suggest, search):
        barrier = threading.Barrier(3)

        def find_places(query, *args):
            if query != "うどん レストラン":
                barrier.wait(timeout=3)
            return []

        search.side_effect = find_places
        response = self.client.post("/results", data=FORM)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(search.call_count, 4)

    def test_mood_confirmation_is_not_displayed(self):
        text = self.client.get("/").get_data(as_text=True)
        self.assertNotIn('name="include_mood"', text)
        self.assertNotIn('id="mood-search-confirm"', text)

    @patch("apps.home.views.urlopen")
    def test_direct_link_does_not_call_ollama(self, urlopen):
        response = self.client.get("/results")
        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/" class="results-back-link">← ホームに戻る</a>', response.get_data(as_text=True))
        urlopen.assert_not_called()

    @patch("apps.home.views.search_places")
    @patch("apps.home.views.suggest_searches")
    def test_free_search_uses_keyword_genre_and_budget_without_ai(self, suggest, search):
        search.return_value = [{"id": "p1", "name": "カレー店", "address": "東京", "distance": 10, "distance_exact": 10,
                                "rating": 4.5, "price": "普通", "url": "", "attributions": []}]
        response = self.client.post("/results", data={
            "keyword": " カレー店 ", "genre": "洋", "budget": "1500",
            "latitude": "35.68", "longitude": "139.76",
        })
        self.assertEqual(response.status_code, 200)
        search.assert_called_once_with("カレー店 洋食", 1500, 35.68, 139.76)
        suggest.assert_not_called()
        text = response.get_data(as_text=True)
        self.assertIn("カレー店", text)
        self.assertIn('href="/restaurants/detail/p1"', text)
        self.assertNotIn("元気ラーメン", text)

    @patch("apps.home.views.search_places", return_value=[])
    @patch("apps.home.views.suggest_searches")
    def test_free_search_without_genre_or_budget(self, suggest, search):
        response = self.client.post("/results", data={
            "keyword": "寿司", "latitude": "35.68", "longitude": "139.76",
        })
        self.assertEqual(response.status_code, 200)
        search.assert_called_once_with("寿司", None, 35.68, 139.76)
        self.assertIn("条件に合う店舗が見つかりませんでした", response.get_data(as_text=True))
        suggest.assert_not_called()

    @patch("apps.home.views.suggest_searches", return_value=SUGGESTIONS)
    @patch("apps.home.places.places_request")
    def test_both_search_modes_only_display_places_within_radius(self, places_request, suggest):
        places_request.return_value = {"places": [
            {"id": "inside", "displayName": {"text": "圏内の店"},
             "location": {"latitude": 0, "longitude": 0}},
            {"id": "outside", "displayName": {"text": "圏外の店"},
             "location": {"latitude": math.degrees(10001 / 6371000), "longitude": 0}},
            {"id": "unknown", "displayName": {"text": "距離不明の店"}},
        ]}
        for search in ({"dishName": "さっぱり"}, {"keyword": "寿司"}):
            with self.subTest(search=search):
                response = self.client.post("/results", data={
                    **search, "latitude": "0", "longitude": "0",
                })
                self.assertEqual(response.status_code, 200)
                text = response.get_data(as_text=True)
                self.assertIn("圏内の店", text)
                self.assertNotIn("圏外の店", text)
                self.assertNotIn("距離不明の店", text)

    def test_radius_choices_are_not_on_search_forms(self):
        text = self.client.get("/").get_data(as_text=True)
        self.assertNotIn('name="radius"', text)

    @patch("apps.home.views.suggest_searches", return_value=SUGGESTIONS)
    @patch("apps.home.places.places_request")
    def test_both_search_results_offer_filter_with_precise_distances(self, places_request, suggest):
        places_request.return_value = {"places": [
            {"id": "inside", "displayName": {"text": "圏内の店"},
             "location": {"latitude": math.degrees(1000.1 / 6371000), "longitude": 0}},
        ]}
        for search in ({"dishName": "さっぱり"}, {"keyword": "寿司"}):
            with self.subTest(search=search):
                places_request.reset_mock()
                response = self.client.post("/results", data={
                    **search, "latitude": "0", "longitude": "0",
                })
                self.assertEqual(response.status_code, 200)
                text = response.get_data(as_text=True)
                select = text.split('id="distanceFilter" disabled>', 1)[1].split("</select>", 1)[0]
                for radius in ("1", "3", "5", "10"):
                    selected = " selected" if radius == "10" else ""
                    self.assertIn(f'<option value="{radius}"{selected}>{radius}km以内</option>', select)
                distance = re.search(r'data-distance="([^"]+)"', text)
                self.assertIsNotNone(distance)
                self.assertAlmostEqual(float(distance.group(1)), 1000.1)
                self.assertIn("約1000m", text)
                self.assertTrue(places_request.called)
                for call in places_request.call_args_list:
                    self.assertEqual(call.args[2]["locationBias"]["circle"]["radius"], 10000)

    @patch("apps.home.views.search_places")
    @patch("apps.home.views.suggest_searches")
    def test_invalid_free_search_is_visible(self, suggest, search):
        for update in ({"keyword": " "}, {"keyword": "あ" * 201}, {"genre": "bad"},
                       {"budget": "-1"}, {"latitude": "NaN"}):
            with self.subTest(update=update):
                response = self.client.post("/results", data={
                    "keyword": "寿司", "latitude": "35.68", "longitude": "139.76", **update,
                })
                self.assertEqual(response.status_code, 400)
                self.assertNotIn("元気ラーメン", response.get_data(as_text=True))
        search.assert_not_called()
        suggest.assert_not_called()

    @patch("apps.home.views.search_places", side_effect=PlacesAPIError(400, ["API_KEY_INVALID"]))
    def test_free_search_api_error_is_visible(self, search):
        response = self.client.post("/results", data={
            "keyword": "寿司", "latitude": "35.68", "longitude": "139.76",
        })
        self.assertEqual(response.status_code, 503)
        self.assertIn("APIキーが無効", response.get_data(as_text=True))
        self.assertNotIn("元気ラーメン", response.get_data(as_text=True))

    @patch("apps.home.views.urlopen")
    def test_invalid_input_does_not_call_ollama(self, urlopen):
        for update in ({"dishName": " "}, {"dishName": "あ" * 201},
                       {"genre": "unknown"}, {"budget": "-1"}, {"budget": "1.5"}):
            with self.subTest(update=update):
                response = self.client.post("/results", data={**FORM, **update})
                self.assertEqual(response.status_code, 400)
        urlopen.assert_not_called()

    @patch("apps.home.views.search_places")
    @patch("apps.home.views.suggest_searches", return_value=SUGGESTIONS)
    def test_invalid_location_is_visible(self, suggest, places):
        for latitude in ("", "NaN", "91"):
            response = self.client.post("/results", data={**FORM, "latitude": latitude})
            self.assertEqual(response.status_code, 400)
            self.assertIn("現在地の取得が必要", response.get_data(as_text=True))
        places.assert_not_called()
        suggest.assert_not_called()

    @patch("apps.home.views.search_places")
    @patch("apps.home.views.urlopen", side_effect=URLError("unavailable"))
    def test_ollama_failure_is_visible_and_searches_input(self, urlopen, search):
        search.return_value = [{"id": "p1", "name": "入力から見つかった店", "address": "",
                                "distance": 10, "distance_exact": 10, "rating": None,
                                "price": "不明", "url": "", "attributions": []}]
        response = self.client.post("/results", data=FORM)
        self.assertEqual(response.status_code, 503)
        self.assertIn("AIの提案を取得できませんでした", response.get_data(as_text=True))
        self.assertIn("入力から見つかった店", response.get_data(as_text=True))
        self.assertNotIn('<details class="ai-recommendation">', response.get_data(as_text=True))
        search.assert_called_once_with("さっぱり 和食", 12345, 35.68, 139.76)

    @patch("apps.home.views.search_places", return_value=[])
    @patch("apps.home.views.urlopen")
    def test_invalid_model_output_is_visible(self, urlopen, search):
        invalid_outputs = [
            {"suggestions": []},
            {"suggestions": [{"name": "", "reason": "理由"}, *SUGGESTIONS[1:]]},
        ]
        for output in invalid_outputs:
            with self.subTest(output=output):
                urlopen.return_value.__enter__.return_value = json_response({"response": json.dumps(output)})
                response = self.client.post("/results", data=FORM)
                self.assertEqual(response.status_code, 503)
                self.assertIn("AIの提案を取得できませんでした", response.get_data(as_text=True))
        self.assertEqual(search.call_count, len(invalid_outputs))
        for call in search.call_args_list:
            self.assertEqual(call.args[0], "さっぱり 和食")

    @patch("apps.home.views.search_places")
    @patch("apps.home.views.suggest_searches", return_value=SUGGESTIONS)
    def test_places_are_deduplicated_and_failures_are_visible(self, suggest, search):
        place = {"id": "p1", "name": "<店>", "address": "東京", "distance": 10, "distance_exact": 10,
                 "rating": 4.5, "price": "普通", "url": "", "attributions": []}
        def find_places(query, *args):
            if query == "寿司 レストラン":
                raise URLError("unavailable")
            return [place] if query in ("うどん レストラン", "そば レストラン") else []

        search.side_effect = find_places
        response = self.client.post("/results", data=FORM)
        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(text.count("<h3>&lt;店&gt;</h3>"), 1)
        self.assertIn('href="/restaurants/detail/p1"', text)
        self.assertIn("店舗を検索できませんでした", text)
        self.assertNotIn("元気ラーメン", text)

    @patch("apps.home.views.search_places", side_effect=PlacesAPIError(400, ["API_KEY_INVALID"]))
    @patch("apps.home.views.suggest_searches", return_value=SUGGESTIONS)
    def test_invalid_key_error_is_visible_and_stops_retries(self, suggest, search):
        response = self.client.post("/results", data=FORM)
        self.assertEqual(response.status_code, 503)
        self.assertIn("APIキーが無効", response.get_data(as_text=True))
        self.assertEqual(search.call_count, 1)

    @patch("apps.home.views.search_places")
    @patch("apps.home.views.suggest_searches", return_value=SUGGESTIONS)
    def test_parallel_failures_are_logged_and_first_api_error_is_shown(self, suggest, search):
        place = {"id": "p1", "name": "先の店", "address": "", "distance": 10, "distance_exact": 10,
                 "rating": None, "price": "不明", "url": "", "attributions": []}
        def find_places(query, *args):
            if query in ("うどん レストラン", "さっぱり 和食"):
                return [place]
            if query == "そば レストラン":
                raise PlacesAPIError(400, ["API_KEY_INVALID"])
            raise URLError("unavailable")

        search.side_effect = find_places
        with self.assertLogs(self.client.application.logger.name, level="ERROR") as logs:
            response = self.client.post("/results", data=FORM)
        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 503)
        self.assertIn("APIキーが無効", text)
        self.assertIn("先の店", text)
        self.assertTrue(any("API_KEY_INVALID" in entry for entry in logs.output))
        self.assertTrue(any("店舗検索に失敗しました" in entry for entry in logs.output))
        self.assertEqual(search.call_count, 4)


class RecipeSearchTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add_all([
            Recipe_list(recipe_name="トマトパスタ", ingredients="トマト\n麺", description="煮込む"),
            Recipe_list(recipe_name="卵料理", ingredients="卵", description="トマトを添える"),
            Recipe_list(recipe_name="100%スープ", ingredients="野菜", description="煮る"),
        ])
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_home_has_outside_and_recipe_forms(self):
        text = self.client.get("/").get_data(as_text=True)
        self.assertIn("外で食べる", text)
        self.assertIn("家で食べる", text)
        self.assertIn('action="/recipe-results" method="get" id="home-recipes"', text)
        self.assertNotIn("フリー検索", text)

    @patch("apps.home.views.search_places")
    @patch("apps.home.views.suggest_searches")
    def test_search_matches_recipe_fields_without_location_or_external_apis(self, suggest, places):
        for keyword, expected in (("パスタ", "トマトパスタ"), ("麺", "トマトパスタ"), ("添える", "卵料理")):
            with self.subTest(keyword=keyword):
                response = self.client.get("/recipe-results", query_string={"keyword": keyword})
                self.assertEqual(response.status_code, 200)
                self.assertIn(expected, response.get_data(as_text=True))
        text = self.client.get("/recipe-results", query_string={"keyword": "パスタ"}).get_data(as_text=True)
        self.assertIn("トマト\n麺", text)
        self.assertIn("煮込む", text)
        self.assertNotIn("卵料理", text)
        self.assertIn('href="/recipes/', text)
        suggest.assert_not_called()
        places.assert_not_called()

    def test_search_treats_wildcards_as_literals_and_escapes_results(self):
        db.session.add(Recipe_list(recipe_name="<100%>", ingredients="水", description="混ぜる"))
        db.session.commit()
        text = self.client.get("/recipe-results", query_string={"keyword": "%"}).get_data(as_text=True)
        self.assertIn("100%スープ", text)
        self.assertIn("&lt;100%&gt;", text)
        self.assertNotIn("トマトパスタ", text)

    def test_empty_invalid_and_no_results(self):
        for keyword in (" ", "あ" * 201):
            response = self.client.get("/recipe-results", query_string={"keyword": keyword})
            self.assertEqual(response.status_code, 400)
            self.assertIn("キーワードを200文字以内", response.get_data(as_text=True))
        response = self.client.get("/recipe-results", query_string={"keyword": "不存在"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("条件に合うレシピが見つかりませんでした", response.get_data(as_text=True))
        self.assertIn('href="/" class="results-back-link">← ホームに戻る</a>', response.get_data(as_text=True))


class PlacesTests(unittest.TestCase):
    def test_budget_boundaries(self):
        for budget, count in ((0, 1), (999, 1), (1000, 2), (2999, 2),
                              (3000, 3), (9999, 3), (10000, 4)):
            with self.subTest(budget=budget):
                self.assertEqual(len(budget_price_levels(budget)), count)

    @patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "test-key"})
    @patch("apps.home.places.urlopen")
    def test_search_request_and_results(self, urlopen):
        urlopen.return_value.__enter__.return_value = json_response({"places": [{
            "id": "id1", "displayName": {"text": "店"}, "formattedAddress": "住所",
            "location": {"latitude": 35.68, "longitude": 139.76},
            "priceLevel": "PRICE_LEVEL_MODERATE", "rating": 4.2,
            "googleMapsUri": "https://maps.google.com/?cid=1",
            "attributions": [{"provider": "提供元", "providerUri": "https://example.com"}],
        }]})
        places = search_places("うどん レストラン", 1500, 35.68, 139.76)
        api_request = urlopen.call_args.args[0]
        payload = json.loads(api_request.data)
        self.assertEqual(payload["textQuery"], "うどん レストラン")
        self.assertEqual(payload["priceLevels"], ["PRICE_LEVEL_INEXPENSIVE", "PRICE_LEVEL_MODERATE"])
        self.assertEqual(payload["locationBias"]["circle"]["center"], {"latitude": 35.68, "longitude": 139.76})
        self.assertEqual(payload["locationBias"]["circle"]["radius"], 10000)
        self.assertEqual(places[0]["distance"], 0)
        self.assertEqual(places[0]["price"], "普通")
        self.assertEqual(places[0]["attributions"][0]["name"], "提供元")

    @patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "test-key"})
    @patch("apps.home.places.urlopen")
    def test_search_filters_outside_radius_and_unknown_distances_before_rounding(self, urlopen):
        def place(name, distance):
            item = {"id": name, "displayName": {"text": name}}
            if distance is not None:
                item["location"] = {
                    "latitude": math.degrees(distance / 6371000),
                    "longitude": 0,
                }
            return item

        urlopen.return_value.__enter__.return_value = json_response({"places": [
            place("inside", 9999.9),
            place("boundary", 10000),
            place("outside", 10000.1),
            place("unknown", None),
        ]})

        places = search_places("test", None, 0, 0)
        self.assertEqual([place["id"] for place in places], ["inside", "boundary"])
        self.assertEqual(places[0]["distance"], 10000)

    @patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "test-key"})
    @patch("apps.home.places.urlopen")
    def test_no_budget_and_empty_results(self, urlopen):
        urlopen.return_value.__enter__.return_value = json_response({})
        self.assertEqual(search_places("そば", None, 35.68, 139.76), [])
        self.assertNotIn("priceLevels", json.loads(urlopen.call_args.args[0].data))

    @patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": ""})
    def test_missing_key_fails(self):
        with self.assertRaises(ValueError):
            search_places("そば", None, 35.68, 139.76)

    @patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "test-key"})
    @patch("apps.home.places.urlopen")
    def test_details_request_and_missing_optional_fields(self, urlopen):
        urlopen.return_value.__enter__.return_value = json_response({
            "id": "test-id", "displayName": {"text": "実店舗"},
            "regularOpeningHours": {"weekdayDescriptions": ["月曜日: 9:00～17:00"]},
            "websiteUri": "javascript:alert(1)",
        })
        place = place_details("test-id")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.full_url, "https://places.googleapis.com/v1/places/test-id?languageCode=ja&regionCode=JP")
        self.assertIn("regularOpeningHours", request.get_header("X-goog-fieldmask"))
        self.assertEqual(place["hours"], ["月曜日: 9:00～17:00"])
        self.assertEqual(place["price"], "不明")
        self.assertEqual(place["website"], "")

    @patch("apps.home.places.urlopen")
    def test_invalid_place_id_rejected_before_request(self, urlopen):
        with self.assertRaises(ValueError):
            place_details("../bad")
        urlopen.assert_not_called()

    @patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "test-key"})
    @patch("apps.home.places.urlopen")
    def test_photo_metadata_and_media_request(self, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.read.side_effect = [
            json.dumps({
                "id": "test-id", "displayName": {"text": "店"},
                "photos": [{"name": "places/test-id/photos/abc-123",
                            "googleMapsUri": "https://maps.google.com/photo",
                            "authorAttributions": [{"displayName": "作者", "uri": "//maps.google.com/contrib/1",
                                                    "photoUri": "//lh3.googleusercontent.com/avatar"}]}],
            }).encode("utf-8"),
            json.dumps({"photoUri": "https://lh3.googleusercontent.com/image"}).encode("utf-8"),
        ]
        place = place_details("test-id")
        self.assertIn("photos", urlopen.call_args.args[0].get_header("X-goog-fieldmask"))
        self.assertEqual(place["photo"]["authors"][0]["url"], "https://maps.google.com/contrib/1")
        self.assertEqual(photo_url(place["photo"]), "https://lh3.googleusercontent.com/image")
        self.assertIn("/places/test-id/photos/abc-123/media?", urlopen.call_args.args[0].full_url)
        self.assertNotIn("test-key", urlopen.call_args.args[0].full_url)

    @patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "test-key"})
    @patch("apps.home.places.urlopen")
    def test_rejects_mismatched_photo_name(self, urlopen):
        urlopen.return_value.__enter__.return_value = json_response({
            "id": "test-id", "displayName": {"text": "店"},
            "photos": [{"name": "places/other/photos/abc"}],
        })
        with self.assertRaises(ValueError):
            place_details("test-id")

    @patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "test-key"})
    @patch("apps.home.places.urlopen")
    def test_http_error_extracts_reason_without_exposing_message(self, urlopen):
        body = {"error": {"message": "secret test-key", "details": [
            {"reason": "API_KEY_INVALID"}, {"reason": "secret test-key"}]}}
        urlopen.side_effect = HTTPError("https://places.googleapis.com", 400, "Bad Request", {}, json_response(body))
        with self.assertRaises(PlacesAPIError) as context:
            search_places("そば", None, 35.68, 139.76)
        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.reasons, ["API_KEY_INVALID"])
        self.assertNotIn("test-key", str(context.exception))


class RestaurantDetailTests(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.config["TESTING"] = True
        self.client = app.test_client()

    @patch("apps.restaurants.views.place_details")
    def test_selected_place_is_displayed_without_sample_content(self, details):
        details.return_value = {
            "name": "<実店舗>", "address": "実際の住所", "rating": 4.2,
            "price": "普通", "phone": "", "hours": ["月曜日 休業"],
            "website": "", "url": "", "attributions": [{"name": "提供者", "url": ""}], "photo": None,
        }
        response = self.client.get("/restaurants/detail/place123")
        text = response.get_data(as_text=True)
        details.assert_called_once_with("place123")
        self.assertEqual(response.status_code, 200)
        self.assertIn("&lt;実店舗&gt;", text)
        self.assertIn("実際の住所", text)
        self.assertIn("月曜日 休業", text)
        self.assertIn("提供者", text)
        self.assertIn('alt="Google Maps"', text)
        self.assertIn("img/NoImage.jpg", text)
        self.assertNotIn("元気ラーメン", text)
        self.assertIn('class="hero"', text)
        self.assertIn('class="hero-image"', text)
        self.assertIn('class="review-section"', text)
        self.assertIn('class="button button-primary reservation-button" disabled', text)
        self.assertIn('class="favorite-button" disabled', text)
        self.assertIn('class="review-button" disabled', text)
        self.assertIn("レビューの表示・投稿は未対応です。", text)
        self.assertNotIn("スープが濃厚で、とてもおいしかったです。", text)
        self.assertEqual(text.count("back-to-results"), 3)

    @patch("apps.restaurants.views.photo_url", return_value="https://lh3.googleusercontent.com/image")
    @patch("apps.restaurants.views.place_details")
    def test_photo_and_author_displayed(self, details, photo):
        details.return_value = {
            "name": "実店舗", "address": "", "rating": None, "price": "不明", "phone": "",
            "hours": [], "website": "", "url": "", "attributions": [],
            "photo": {"name": "places/test/photos/photo", "source": "https://maps.google.com/photo",
                      "authors": [{"name": "写真作者", "url": "https://maps.google.com/contrib/1",
                                   "avatar": "https://lh3.googleusercontent.com/avatar"}]},
        }
        response = self.client.get("/restaurants/detail/test")
        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("https://lh3.googleusercontent.com/image", text)
        self.assertIn("写真作者", text)
        self.assertIn("https://maps.google.com/photo", text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        photo.assert_called_once_with(details.return_value["photo"])

    @patch("apps.restaurants.views.photo_url", side_effect=PlacesAPIError(429, []))
    @patch("apps.restaurants.views.place_details")
    def test_photo_failure_is_visible_with_fallback(self, details, photo):
        details.return_value = {
            "name": "実店舗", "address": "", "rating": None, "price": "不明", "phone": "",
            "hours": [], "website": "", "url": "", "attributions": [],
            "photo": {"name": "places/test/photos/photo", "source": "", "authors": []},
        }
        response = self.client.get("/restaurants/detail/test")
        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("店舗写真を取得できませんでした。", text)
        self.assertIn("img/NoImage.jpg", text)

    @patch("apps.restaurants.views.place_details", side_effect=PlacesAPIError(403, []))
    def test_api_error_does_not_show_sample_as_real(self, details):
        response = self.client.get("/restaurants/detail/place123")
        self.assertEqual(response.status_code, 503)
        self.assertIn("店舗情報を取得できませんでした", response.get_data(as_text=True))
        self.assertNotIn("元気ラーメン", response.get_data(as_text=True))

    def test_sample_route_remains_unchanged(self):
        response = self.client.get("/restaurants/detail")
        self.assertEqual(response.status_code, 200)
        self.assertIn("元気ラーメン", response.get_data(as_text=True))
        self.assertIn("予約する", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
