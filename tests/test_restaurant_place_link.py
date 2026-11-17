import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from apps import create_app
from apps.auth.models import Account
from apps.extensions import db
from apps.restaurants.models import RestaurantPlaceClaim


PLACE = {
    "id": "place-123",
    "name": "テスト食堂",
    "address": "東京都千代田区",
    "distance": 100,
    "distance_exact": 100,
    "rating": 4.0,
    "price": "普通",
    "url": "",
    "attributions": [],
}


class RestaurantPlaceLinkTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "place-links.sqlite"
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + database_path.as_posix(),
            "PLACE_LINK_DEMO_MODE": True,
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            self.restaurant = Account(
                email="restaurant@example.com",
                password_hash="unused",
                account_type="restaurant",
                name="テスト食堂",
                phone="03-1234-5678",
            )
            self.other_restaurant = Account(
                email="other@example.com",
                password_hash="unused",
                account_type="restaurant",
                name="別の店舗",
            )
            self.user = Account(
                email="user@example.com",
                password_hash="unused",
                account_type="user",
                name="一般ユーザー",
            )
            db.session.add_all([
                self.restaurant,
                self.other_restaurant,
                self.user,
            ])
            db.session.commit()
            self.restaurant_email = self.restaurant.email
            self.other_restaurant_email = self.other_restaurant.email
            self.user_email = self.user.email

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def login_as(self, email):
        account_type = "user" if email == self.user_email else "restaurant"
        with self.client.session_transaction() as session:
            session["email"] = email
            session["account_type"] = account_type

    @patch("apps.restaurants.views.place_details", return_value={"phone": "03-1234-5678"})
    def test_demo_code_links_place_to_restaurant_account(self, place_details):
        self.login_as(self.restaurant_email)
        response = self.client.post(
            "/restaurants/api/place-claims",
            json={"place_id": PLACE["id"]},
        )

        self.assertEqual(response.status_code, 201)
        result = response.get_json()
        self.assertEqual(result["phone_last4"], "5678")
        self.assertTrue(result["demo"])
        self.assertRegex(result["demo_code"], r"^[0-9]{6}$")
        place_details.assert_called_once_with(PLACE["id"])
        with self.app.app_context():
            claim = RestaurantPlaceClaim.query.one()
            self.assertNotEqual(claim.code_hash, result["demo_code"])
            self.assertEqual(claim.place_id, PLACE["id"])

        verified = self.client.post(
            "/restaurants/api/place-claims/verify",
            json={"code": result["demo_code"]},
        )
        self.assertEqual(verified.status_code, 200)
        with self.app.app_context():
            account = Account.query.filter_by(email=self.restaurant_email).one()
            self.assertEqual(account.place_id, PLACE["id"])
            self.assertEqual(RestaurantPlaceClaim.query.count(), 0)
        with self.client.session_transaction() as session:
            self.assertEqual(session["place_id"], PLACE["id"])

    def test_claim_requires_a_restaurant_account_and_a_listed_phone(self):
        response = self.client.post(
            "/restaurants/api/place-claims",
            json={"place_id": PLACE["id"]},
        )
        self.assertEqual(response.status_code, 401)

        self.login_as(self.user_email)
        response = self.client.post(
            "/restaurants/api/place-claims",
            json={"place_id": PLACE["id"]},
        )
        self.assertEqual(response.status_code, 403)

        self.login_as(self.restaurant_email)
        with patch("apps.restaurants.views.place_details", return_value={"phone": ""}):
            response = self.client.post(
                "/restaurants/api/place-claims",
                json={"place_id": PLACE["id"]},
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"],
            "Placesに店舗電話番号が掲載されていません。",
        )

    @patch("apps.restaurants.views.place_details", return_value={"phone": "03-1234-5678"})
    def test_wrong_codes_are_limited_and_expire(self, place_details):
        self.login_as(self.restaurant_email)
        response = self.client.post(
            "/restaurants/api/place-claims",
            json={"place_id": PLACE["id"]},
        )
        self.assertEqual(response.status_code, 201)
        demo_code = response.get_json()["demo_code"]
        wrong_code = "000000" if demo_code != "000000" else "000001"

        for attempt in range(5):
            response = self.client.post(
                "/restaurants/api/place-claims/verify",
                json={"code": "１２３４５６" if attempt == 0 else wrong_code},
            )
        self.assertEqual(response.status_code, 429)
        with self.app.app_context():
            self.assertEqual(RestaurantPlaceClaim.query.count(), 0)

        self.client.post(
            "/restaurants/api/place-claims",
            json={"place_id": PLACE["id"]},
        )
        self.assertEqual(place_details.call_count, 2)
        with self.app.app_context():
            claim = RestaurantPlaceClaim.query.one()
            claim.expires_at = datetime.now() - timedelta(seconds=1)
            db.session.commit()
        expired = self.client.post(
            "/restaurants/api/place-claims/verify",
            json={"code": "123456"},
        )
        self.assertEqual(expired.status_code, 410)

    @patch("apps.restaurants.views.place_details", return_value={"phone": "03-1234-5678"})
    def test_place_already_linked_to_another_account_cannot_be_claimed(self, place_details):
        with self.app.app_context():
            account = Account.query.filter_by(
                email=self.other_restaurant_email,
            ).one()
            account.place_id = PLACE["id"]
            db.session.commit()
        self.login_as(self.restaurant_email)
        response = self.client.post(
            "/restaurants/api/place-claims",
            json={"place_id": PLACE["id"]},
        )
        self.assertEqual(response.status_code, 409)
        place_details.assert_not_called()

    @patch("apps.home.views.search_places", return_value=[PLACE])
    def test_linked_place_is_marked_in_search_results(self, search_places):
        search_places.return_value = [dict(PLACE)]
        with self.app.app_context():
            account = Account.query.filter_by(
                email=self.restaurant_email,
            ).one()
            account.place_id = PLACE["id"]
            db.session.commit()
        response = self.client.post("/results", data={
            "keyword": "食堂",
            "latitude": "35.68",
            "longitude": "139.76",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("店舗アカウント連携済み（デモ）", response.get_data(as_text=True))
        search_places.assert_called_once()

    @patch("apps.home.views.search_places", return_value=[PLACE])
    def test_restaurant_can_start_link_from_search_results(self, search_places):
        search_places.return_value = [dict(PLACE)]
        self.login_as(self.restaurant_email)
        response = self.client.post("/results", data={
            "keyword": "食堂",
            "latitude": "35.68",
            "longitude": "139.76",
        })
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertIn("この店舗をアカウントに連携", text)
        self.assertIn('id="place-claim-dialog"', text)
        search_places.assert_called_once()


if __name__ == "__main__":
    unittest.main()
