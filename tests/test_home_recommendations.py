import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from apps import create_app
from apps.home.places import PlacesAPIError, budget_price_levels, photo_url, place_details, search_places


DISHES = [
    {"name": "うどん", "reason": "さっぱり"},
    {"name": "そば", "reason": "軽い"},
    {"name": "寿司", "reason": "食べやすい"},
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
        app = create_app()
        app.config["TESTING"] = True
        self.client = app.test_client()

    @patch("apps.home.views.search_places", return_value=[])
    @patch("apps.home.views.urlopen")
    def test_sends_mood_and_genre_but_not_budget_or_location_to_ollama(self, urlopen, places):
        urlopen.return_value.__enter__.return_value = json_response({"response": json.dumps({"dishes": DISHES})})
        response = self.client.post("/results", data=FORM)
        self.assertEqual(response.status_code, 200)
        self.assertIn("うどん", response.get_data(as_text=True))
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertIn("さっぱり", payload["prompt"])
        self.assertIn("料理ジャンル: 和", payload["prompt"])
        self.assertNotIn("12345", payload["prompt"])
        self.assertNotIn("35.68", payload["prompt"])
        self.assertEqual([call.args[0] for call in places.call_args_list], ["うどん レストラン", "そば レストラン", "寿司 レストラン"])
        self.assertEqual(places.call_args.args[1:], (12345, 35.68, 139.76))

    @patch("apps.home.views.urlopen")
    def test_direct_link_does_not_call_ollama(self, urlopen):
        self.assertEqual(self.client.get("/results").status_code, 200)
        urlopen.assert_not_called()

    @patch("apps.home.views.search_places")
    @patch("apps.home.views.suggest_dishes")
    def test_free_search_uses_keyword_genre_and_budget_without_ai(self, suggest, search):
        search.return_value = [{"id": "p1", "name": "カレー店", "address": "東京", "distance": 10,
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
    @patch("apps.home.views.suggest_dishes")
    def test_free_search_without_genre_or_budget(self, suggest, search):
        response = self.client.post("/results", data={
            "keyword": "寿司", "latitude": "35.68", "longitude": "139.76",
        })
        self.assertEqual(response.status_code, 200)
        search.assert_called_once_with("寿司", None, 35.68, 139.76)
        self.assertIn("条件に合う店舗が見つかりませんでした", response.get_data(as_text=True))
        suggest.assert_not_called()

    @patch("apps.home.views.search_places")
    @patch("apps.home.views.suggest_dishes")
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
    @patch("apps.home.views.suggest_dishes", return_value=DISHES)
    def test_invalid_location_is_visible(self, suggest, places):
        for latitude in ("", "NaN", "91"):
            response = self.client.post("/results", data={**FORM, "latitude": latitude})
            self.assertEqual(response.status_code, 400)
            self.assertIn("現在地の取得が必要", response.get_data(as_text=True))
        places.assert_not_called()
        suggest.assert_not_called()

    @patch("apps.home.views.urlopen", side_effect=URLError("unavailable"))
    def test_ollama_failure_is_visible(self, urlopen):
        response = self.client.post("/results", data=FORM)
        self.assertEqual(response.status_code, 503)
        self.assertIn("AIの提案を取得できませんでした", response.get_data(as_text=True))

    @patch("apps.home.views.urlopen")
    def test_invalid_model_output_is_visible(self, urlopen):
        urlopen.return_value.__enter__.return_value = json_response({"response": '{"dishes":[]}'})
        response = self.client.post("/results", data=FORM)
        self.assertEqual(response.status_code, 503)
        self.assertIn("AIの提案を取得できませんでした", response.get_data(as_text=True))

    @patch("apps.home.views.search_places")
    @patch("apps.home.views.suggest_dishes", return_value=DISHES)
    def test_places_are_deduplicated_and_failures_are_visible(self, suggest, search):
        place = {"id": "p1", "name": "<店>", "address": "東京", "distance": 10,
                 "rating": 4.5, "price": "普通", "url": "", "attributions": []}
        search.side_effect = [[place], [place], URLError("unavailable")]
        response = self.client.post("/results", data=FORM)
        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(text.count("<h3>&lt;店&gt;</h3>"), 1)
        self.assertIn('href="/restaurants/detail/p1"', text)
        self.assertIn("店舗を検索できませんでした", text)
        self.assertNotIn("元気ラーメン", text)

    @patch("apps.home.views.search_places", side_effect=PlacesAPIError(400, ["API_KEY_INVALID"]))
    @patch("apps.home.views.suggest_dishes", return_value=DISHES)
    def test_invalid_key_error_is_visible_and_stops_retries(self, suggest, search):
        response = self.client.post("/results", data=FORM)
        self.assertEqual(response.status_code, 503)
        self.assertIn("APIキーが無効", response.get_data(as_text=True))
        self.assertEqual(search.call_count, 1)


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
        self.assertEqual(places[0]["distance"], 0)
        self.assertEqual(places[0]["price"], "普通")
        self.assertEqual(places[0]["attributions"][0]["name"], "提供元")

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
