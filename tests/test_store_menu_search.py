import unittest
from unittest.mock import patch
from urllib.error import URLError

from sqlalchemy.exc import SQLAlchemyError

from apps import create_app
from apps.auth.models import Account
from apps.extensions import db
from apps.home.places import search_place_by_id
from apps.restaurants.models import RestaurantMenu
from apps.review_models import ContentReview


def place(place_id, name, distance):
    return {
        "id": place_id,
        "name": name,
        "address": "東京都",
        "distance": distance,
        "distance_exact": distance,
        "rating": None,
        "price": "不明",
        "url": "",
        "attributions": [],
    }


class StoreMenuSearchTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        accounts = [
            Account(email="one@example.com", name="店舗1", account_type="restaurant", password_hash="x", place_id="store1"),
            Account(email="two@example.com", name="店舗2", account_type="restaurant", password_hash="x", place_id="store2"),
            Account(email="three@example.com", name="店舗3", account_type="restaurant", password_hash="x", place_id="store3"),
            Account(email="unlinked@example.com", name="未連携", account_type="restaurant", password_hash="x"),
        ]
        db.session.add_all(accounts)
        db.session.flush()
        db.session.add_all([
            RestaurantMenu(restaurant_id=accounts[0].id, name="アンパン", price=150, calories=200),
            RestaurantMenu(restaurant_id=accounts[1].id, name="パン", price=300, calories=200),
            RestaurantMenu(restaurant_id=accounts[2].id, name="うどん", price=400, calories=200),
            RestaurantMenu(restaurant_id=accounts[3].id, name="パン", price=100, calories=200),
        ])
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.context.pop()

    @patch("apps.home.views.search_place_by_id")
    @patch("apps.home.views.search_places", return_value=[])
    def test_bidirectional_menu_matching_without_google_search_results(self, search, details):
        details.side_effect = lambda place_id, lat, lng: place(place_id, "取得した" + place_id, 200)
        for keyword in ("パン", "アンパン"):
            with self.subTest(keyword=keyword):
                details.reset_mock()
                response = self.client.get("/results", query_string={
                    "keyword": keyword, "latitude": "35.68", "longitude": "139.76",
                })
                self.assertEqual(response.status_code, 200)
                text = response.get_data(as_text=True)
                self.assertIn("取得したstore1", text)
                self.assertIn("取得したstore2", text)
                self.assertIn("アンパン（150円）", text)
                self.assertIn("パン（300円）", text)
                self.assertNotIn("取得したstore3", text)
                self.assertEqual({call.args[0] for call in details.call_args_list}, {"store1", "store2"})

    @patch("apps.home.views.search_place_by_id")
    @patch("apps.home.views.search_places")
    def test_existing_place_is_not_duplicated_and_budget_limits_menu_matches(self, search, details):
        search.return_value = [place("store1", "Google店舗", 100)]
        details.return_value = place("store2", "もう一店舗", 100)
        response = self.client.get("/results", query_string={
            "keyword": "パン", "budget": "200", "latitude": "35.68", "longitude": "139.76",
        })
        text = response.get_data(as_text=True)
        self.assertEqual(text.count('data-place-id="store1"'), 1)
        self.assertIn("アンパン（150円）", text)
        self.assertNotIn("もう一店舗", text)
        details.assert_not_called()

    @patch("apps.home.views.search_place_by_id")
    @patch("apps.home.views.search_places", return_value=[])
    @patch("apps.home.views.suggest_searches", return_value=[])
    def test_distance_filter_and_mood_search(self, suggest, search, details):
        details.side_effect = lambda place_id, lat, lng: place(
            place_id, place_id, 10001 if place_id == "store1" else 500,
        )
        response = self.client.post("/results", data={
            "dishName": "パン", "latitude": "35.68", "longitude": "139.76",
        })
        text = response.get_data(as_text=True)
        self.assertNotIn('data-place-id="store1"', text)
        self.assertIn('data-place-id="store2"', text)
        self.assertIn('data-distance="500"', text)

    @patch("apps.home.views.search_place_by_id", side_effect=URLError("unavailable"))
    @patch("apps.home.views.search_places", return_value=[])
    def test_lookup_failures_are_reported(self, search, details):
        response = self.client.get("/results", query_string={
            "keyword": "パン", "latitude": "35.68", "longitude": "139.76",
        })
        self.assertEqual(response.status_code, 503)
        self.assertIn("店舗情報を取得できませんでした", response.get_data(as_text=True))
        self.assertNotIn("条件に合う店舗が見つかりませんでした", response.get_data(as_text=True))

    @patch("apps.home.views.search_place_by_id")
    @patch("apps.home.views.search_places", return_value=[])
    def test_normalization_and_removed_menu(self, search, details):
        menu = RestaurantMenu.query.filter_by(name="アンパン").one()
        menu.name = "ＢＲＥＡＤ"
        db.session.commit()
        details.return_value = place("store1", "店舗1", 100)
        response = self.client.get("/results", query_string={
            "keyword": "bread", "latitude": "35.68", "longitude": "139.76",
        })
        self.assertIn("ＢＲＥＡＤ（150円）", response.get_data(as_text=True))
        db.session.delete(menu)
        db.session.commit()
        details.reset_mock()
        response = self.client.get("/results", query_string={
            "keyword": "bread", "latitude": "35.68", "longitude": "139.76",
        })
        self.assertNotIn("ＢＲＥＡＤ（150円）", response.get_data(as_text=True))
        details.assert_not_called()

    @patch("apps.home.views.search_place_by_id")
    @patch("apps.home.views.search_places", return_value=[])
    def test_registered_store_preserves_system_review_rating(self, search, details):
        reviewer = Account(email="reviewer@example.com", name="利用者", account_type="user", password_hash="x")
        db.session.add(reviewer)
        db.session.flush()
        db.session.add(ContentReview(account_id=reviewer.id, place_id="store1", rating=4, comment="おいしい"))
        db.session.commit()
        details.side_effect = lambda place_id, lat, lng: place(place_id, place_id, 100)
        response = self.client.get("/results", query_string={
            "keyword": "アンパン", "latitude": "35.68", "longitude": "139.76",
        })
        self.assertIn("4.0 (システム評価・1件)", response.get_data(as_text=True))

    @patch("apps.home.views.search_place_by_id")
    @patch("apps.home.views.search_places", return_value=[])
    def test_unlimited_search_includes_distant_registered_menus(self, search, details):
        details.side_effect = lambda place_id, lat, lng: place(place_id, place_id, 200000)
        response = self.client.get("/results", query_string={
            "keyword": "パン", "latitude": "35.68", "longitude": "139.76", "radius": "unlimited",
        })
        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-place-id="store1"', text)
        self.assertIn('data-place-id="store2"', text)

    @patch("apps.home.views.search_places", return_value=[])
    def test_database_failure_is_reported(self, search):
        with patch.object(db.session, "query", side_effect=SQLAlchemyError("unavailable")):
            response = self.client.get("/results", query_string={
                "keyword": "パン", "latitude": "35.68", "longitude": "139.76",
            })
        self.assertEqual(response.status_code, 503)
        self.assertIn("店舗メニューを検索できませんでした", response.get_data(as_text=True))

    @patch("apps.home.views.search_place_by_id")
    @patch("apps.home.views.search_places", return_value=[])
    def test_no_location_or_invalid_search_is_not_fabricated(self, search, details):
        details.return_value = place("store1", "不明な店舗", None)
        response = self.client.get("/results", query_string={
            "keyword": "アンパン", "latitude": "35.68", "longitude": "139.76",
        })
        self.assertIn("位置情報がないため表示できませんでした", response.get_data(as_text=True))
        self.assertNotIn('data-place-id="store1"', response.get_data(as_text=True))
        details.reset_mock()
        self.client.get("/results", query_string={"keyword": "パン"})
        details.assert_not_called()


class StorePlaceLookupTests(unittest.TestCase):
    @patch("apps.home.places.places_request")
    def test_place_lookup_uses_real_location_and_checks_identity(self, request):
        request.return_value = {
            "id": "store1",
            "displayName": {"text": "店舗"},
            "location": {"latitude": 35.68, "longitude": 139.76},
        }
        result = search_place_by_id("store1", 35.68, 139.76)
        self.assertEqual(result["distance"], 0)
        self.assertIn("location", request.call_args.args[1])
        request.return_value["id"] = "another"
        with self.assertRaises(ValueError):
            search_place_by_id("store1", 35.68, 139.76)
