import re
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from apps import create_app
from apps.auth.models import Account
from apps.extensions import db
from apps.restaurants.models import Reservation, RestaurantLocation, RestaurantMenu


class LocalRestaurantTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True, "SECRET_KEY": "test-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.store = Account(
            email="shop@example.com", name="架空パン屋", account_type="restaurant",
            password_hash="x", address="架空の住所",
        )
        self.other = Account(
            email="other@example.com", name="遠い店舗", account_type="restaurant",
            password_hash="x", address="別の住所",
        )
        self.user = Account(email="user@example.com", name="利用者", account_type="user", password_hash="x")
        db.session.add_all([self.store, self.other, self.user])
        db.session.flush()
        db.session.add_all([
            RestaurantMenu(restaurant_id=self.store.id, name="アンパン", price=150, calories=100),
            RestaurantMenu(restaurant_id=self.other.id, name="パン", price=250, calories=100),
            RestaurantLocation(restaurant_id=self.other.id, latitude=10, longitude=0),
        ])
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.context.pop()

    def login(self, account):
        with self.client.session_transaction() as session:
            session.clear()
            session["email"] = account.email
            session["account_type"] = account.account_type

    def save_location(self, latitude="0", longitude="0"):
        self.login(self.store)
        page = self.client.get("/restaurants/location").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        return self.client.post("/restaurants/location", data={
            "csrf_token": token, "latitude": latitude, "longitude": longitude,
        })

    def test_location_authentication_validation_and_persistence(self):
        self.login(self.user)
        self.assertEqual(self.client.get("/restaurants/location").status_code, 403)
        self.assertEqual(self.save_location("91", "0").status_code, 400)
        self.assertEqual(self.save_location("NaN", "0").status_code, 400)
        self.assertIsNone(db.session.get(RestaurantLocation, self.store.id))
        self.assertEqual(self.save_location().status_code, 302)
        self.assertEqual(db.session.get(RestaurantLocation, self.store.id).latitude, 0)
        page = self.client.get("/restaurants/location").get_data(as_text=True)
        self.assertIn('value="0.0"', page)
        self.assertIn("店舗の位置を保存しました", page)
        self.assertEqual(self.client.post("/restaurants/location", data={
            "latitude": "1", "longitude": "2",
        }).status_code, 400)
        db.session.expire_all()
        self.assertEqual(db.session.get(RestaurantLocation, self.store.id).latitude, 0)

    @patch("apps.home.views.search_places", return_value=[])
    def test_search_unlinked_menus_names_budget_and_distance(self, search):
        self.save_location()
        base = {"latitude": "0", "longitude": "0"}
        response = self.client.get("/results", query_string={**base, "keyword": "パン"})
        text = response.get_data(as_text=True)
        self.assertIn(f'data-place-id="local-store-{self.store.id}"', text)
        self.assertNotIn(f'data-place-id="local-store-{self.other.id}"', text)
        self.assertIn("アンパン（150円）", text)
        self.assertIn("Google未連携", text)
        self.assertNotIn("google-maps-attribution", text)
        text = self.client.get("/results", query_string={
            **base, "keyword": "パン", "radius": "unlimited",
        }).get_data(as_text=True)
        self.assertIn(f'data-place-id="local-store-{self.other.id}"', text)
        text = self.client.get("/results", query_string={
            **base, "keyword": "パン", "radius": "unlimited", "budget": "200",
        }).get_data(as_text=True)
        self.assertNotIn(f'data-place-id="local-store-{self.other.id}"', text)
        text = self.client.get("/results", query_string={
            **base, "keyword": "架空パン屋",
        }).get_data(as_text=True)
        self.assertIn(f'data-place-id="local-store-{self.store.id}"', text)
        RestaurantMenu.query.filter_by(restaurant_id=self.store.id).delete()
        db.session.commit()
        text = self.client.get("/results", query_string={
            **base, "keyword": "架空パン屋",
        }).get_data(as_text=True)
        self.assertIn(f'data-place-id="local-store-{self.store.id}"', text)

    @patch("apps.restaurants.views.analyze_allergens", return_value=[[]])
    @patch("apps.restaurants.views.place_details")
    def test_local_detail_favorites_history_and_demo_reservation(self, details, allergens):
        self.save_location()
        self.login(self.user)
        place_id = f"local-store-{self.store.id}"
        page = self.client.get(f"/restaurants/detail/{place_id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Google未連携", page.get_data(as_text=True))
        self.assertIn(f"/restaurants/reservations/{place_id}/new", page.get_data(as_text=True))
        details.assert_not_called()
        self.client.post(f"/users/favorites/places/{place_id}", data={"action": "add"})
        self.assertIn("架空パン屋", self.client.get("/users/favorites").get_data(as_text=True))
        self.assertIn("架空パン屋", self.client.get("/users/history").get_data(as_text=True))
        form = self.client.get(f"/restaurants/reservations/{place_id}/new").get_data(as_text=True)
        self.assertIn("予約はデモ", form)
        data = {
            "csrf_token": re.search(r'name="csrf_token" value="([^"]+)"', form).group(1),
            "submission_key": re.search(r'name="submission_key" value="([^"]+)"', form).group(1),
            "name": "ヤマダ", "guests": "2",
            "datetime": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
        }
        self.assertEqual(self.client.post(f"/restaurants/reservations/{place_id}/new", data=data).status_code, 302)
        self.assertEqual(Reservation.query.one().restaurant_id, self.store.id)
        self.assertTrue(Reservation.query.one().is_demo)
        self.assertIn("デモ予約（実際の予約ではありません）", self.client.get("/users/").get_data(as_text=True))
        self.login(self.store)
        management = self.client.get("/restaurants/reservations").get_data(as_text=True)
        self.assertIn("ヤマダ", management)
        token = re.search(r'name="csrf_token" value="([^"]+)"', management).group(1)
        reservation = Reservation.query.one()
        self.assertEqual(self.client.post(f"/restaurants/reservations/{reservation.id}/status", data={
            "csrf_token": token, "action": "confirm",
        }).status_code, 302)
        db.session.expire_all()
        self.assertEqual(Reservation.query.one().status, "confirmed")
        self.login(self.user)
        self.app.config["PLACE_LINK_DEMO_MODE"] = False
        self.assertEqual(self.client.get(f"/restaurants/reservations/{place_id}/new").status_code, 404)
        self.assertEqual(self.client.get("/restaurants/detail/local-store-999").status_code, 404)
