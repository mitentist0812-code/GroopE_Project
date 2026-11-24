import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from flask_migrate import upgrade
from sqlalchemy.exc import SQLAlchemyError

from apps import create_app
from apps.auth.models import Account
from apps.extensions import db
from apps.restaurants.models import PlaceFavorite, PlaceViewHistory


PLACE = {
    "name": "履歴の店舗",
    "address": "東京都千代田区",
    "rating": 4.2,
    "price": "普通",
    "phone": "",
    "hours": [],
    "website": "",
    "url": "",
    "attributions": [],
    "photo": None,
}


class PlaceHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "history.sqlite"
        self.config = {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + database_path.as_posix(),
        }
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            db.session.add_all([
                Account(email="one@example.com", name="One", account_type="user", password_hash="x"),
                Account(email="two@example.com", name="Two", account_type="user", password_hash="x"),
                Account(email="shop@example.com", name="Shop", account_type="restaurant", password_hash="x"),
            ])
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def login(self, email):
        with self.client.session_transaction() as session:
            session["email"] = email

    @patch("apps.restaurants.views.place_details", return_value=PLACE)
    @patch("apps.users.views.place_details", return_value=PLACE)
    def test_views_are_persisted_in_order_and_isolated_by_account(self, history_details, details):
        self.login("one@example.com")
        self.assertIn("閲覧した店舗はまだありません。", self.client.get("/users/history").get_data(as_text=True))
        self.client.get("/restaurants/detail/place123")
        self.client.get("/restaurants/detail")
        self.client.get("/restaurants/detail/place123")
        with self.app.app_context():
            account = Account.query.filter_by(email="one@example.com").one()
            db.session.add(PlaceFavorite(account_id=account.id, place_id="place123"))
            db.session.commit()
            self.assertEqual(PlaceViewHistory.query.count(), 3)

        page = self.client.get("/users/history")
        text = page.get_data(as_text=True)
        self.assertEqual(page.headers["Cache-Control"], "no-store")
        self.assertEqual(text.count("履歴の店舗"), 2)
        self.assertLess(text.index("履歴の店舗"), text.index("元気ラーメン"))
        self.assertLess(text.index("元気ラーメン"), text.rindex("履歴の店舗"))
        self.assertIn('href="/restaurants/detail/place123"', text)
        self.assertIn('aria-label="お気に入り">♥', text)
        self.assertIn('alt="Google Maps"', text)
        history_details.assert_called_once_with("place123")

        self.login("two@example.com")
        self.assertNotIn("履歴の店舗", self.client.get("/users/history").get_data(as_text=True))
        self.assertNotIn("元気ラーメン", self.client.get("/users/history").get_data(as_text=True))

        restarted_app = create_app(self.config)
        restarted_client = restarted_app.test_client()
        with restarted_client.session_transaction() as session:
            session["email"] = "one@example.com"
        with patch("apps.users.views.place_details", return_value=PLACE):
            self.assertIn("履歴の店舗", restarted_client.get("/users/history").get_data(as_text=True))
        with restarted_app.app_context():
            db.session.remove()
            db.engine.dispose()

    @patch("apps.restaurants.views.place_details", return_value=PLACE)
    def test_anonymous_and_restaurant_views_not_recorded(self, details):
        self.client.get("/restaurants/detail/place123")
        self.client.get("/restaurants/detail")
        self.assertEqual(self.client.get("/users/history").headers["Location"], "/auth/login")
        self.login("shop@example.com")
        self.client.get("/restaurants/detail/place123")
        self.assertEqual(self.client.get("/users/history").headers["Location"], "/restaurants/")
        with self.app.app_context():
            self.assertEqual(PlaceViewHistory.query.count(), 0)

    @patch("apps.restaurants.views.place_details", side_effect=URLError("unavailable"))
    def test_failed_detail_does_not_create_history(self, details):
        self.login("one@example.com")
        self.assertEqual(self.client.get("/restaurants/detail/place123").status_code, 503)
        with self.app.app_context():
            self.assertEqual(PlaceViewHistory.query.count(), 0)

    @patch("apps.restaurants.views.place_details", return_value=PLACE)
    def test_history_lookup_failure_preserves_record_and_link(self, details):
        self.login("one@example.com")
        self.client.get("/restaurants/detail/place123")
        with patch("apps.users.views.place_details", side_effect=URLError("unavailable")):
            response = self.client.get("/users/history")
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertIn("一部の店舗情報を取得できませんでした", text)
        self.assertIn('href="/restaurants/detail/place123"', text)
        with self.app.app_context():
            self.assertEqual(PlaceViewHistory.query.count(), 1)

    def test_storage_failure_is_reported_on_detail(self):
        self.login("one@example.com")
        with patch.object(db.session, "commit", side_effect=SQLAlchemyError("failure")):
            response = self.client.get("/restaurants/detail")
        self.assertEqual(response.status_code, 200)
        self.assertIn("店舗の閲覧履歴を保存できませんでした", response.get_data(as_text=True))


class PlaceHistoryMigrationTests(unittest.TestCase):
    def test_upgrade_preserves_existing_favorites(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "migration.sqlite"
            app = create_app({
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///" + path.as_posix(),
            })
            with app.app_context():
                upgrade(revision="4c7d9e2a1b5f")
                account = Account(email="one@example.com", name="One", account_type="user", password_hash="x")
                db.session.add(account)
                db.session.flush()
                db.session.add(PlaceFavorite(account_id=account.id, place_id="place123"))
                db.session.commit()
                upgrade()
                self.assertEqual(PlaceFavorite.query.one().place_id, "place123")
                self.assertEqual(PlaceViewHistory.query.count(), 0)
                db.session.remove()
                db.engine.dispose()
