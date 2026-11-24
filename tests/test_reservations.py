import re
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from flask_migrate import upgrade

from apps import create_app
from apps.auth.models import Account
from apps.extensions import db
from apps.restaurants.models import Reservation


PLACE = {
    "name": "店舗A",
    "address": "東京都",
    "rating": None,
    "price": "不明",
    "phone": "",
    "hours": [],
    "website": "",
    "url": "",
    "attributions": [],
    "photo": None,
}


class ReservationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        path = Path(self.temp_dir.name) / "reservations.sqlite"
        self.config = {
            "TESTING": True,
            "SECRET_KEY": "test-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + path.as_posix(),
        }
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            db.session.add_all([
                Account(email="user@example.com", name="利用者", account_type="user", password_hash="x"),
                Account(email="other@example.com", name="別の利用者", account_type="user", password_hash="x"),
                Account(email="shop@example.com", name="店舗A", account_type="restaurant", password_hash="x", place_id="placeA"),
                Account(email="shop2@example.com", name="店舗B", account_type="restaurant", password_hash="x", place_id="placeB"),
            ])
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def login(self, email):
        with self.client.session_transaction() as session:
            session.clear()
            session["email"] = email

    def form_data(self, place_id="placeA"):
        response = self.client.get(f"/restaurants/reservations/{place_id}/new")
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        return {
            "csrf_token": re.search(r'name="csrf_token" value="([^"]+)"', text).group(1),
            "submission_key": re.search(r'name="submission_key" value="([^"]+)"', text).group(1),
            "name": "ヤマダ タロウ",
            "guests": "2",
            "datetime": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
        }

    def management_token(self):
        response = self.client.get("/restaurants/reservations")
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', text).group(1)

    @patch("apps.restaurants.views.place_details", return_value=PLACE)
    def test_only_linked_place_offers_form_for_general_user(self, details):
        self.login("user@example.com")
        linked = self.client.get("/restaurants/detail/placeA").get_data(as_text=True)
        self.assertIn('href="/restaurants/reservations/placeA/new"', linked)
        unlinked = self.client.get("/restaurants/detail/notlinked").get_data(as_text=True)
        self.assertIn("予約対象外", unlinked)
        self.assertEqual(self.client.get("/restaurants/reservations/notlinked/new").status_code, 404)
        self.assertEqual(self.client.post("/restaurants/reservations/notlinked/new", data={}).status_code, 404)
        self.assertIn("予約対象外（サンプル）", self.client.get("/restaurants/detail").get_data(as_text=True))
        self.login("shop@example.com")
        self.assertEqual(self.client.get("/restaurants/reservations/placeA/new").status_code, 403)
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.client.get("/restaurants/reservations/placeA/new").headers["Location"], "/auth/login")

    def test_submission_approval_cancellation_and_account_isolation(self):
        self.login("user@example.com")
        data = self.form_data()
        response = self.client.post("/restaurants/reservations/placeA/new", data=data)
        self.assertEqual(response.headers["Location"], "/users/")
        self.assertEqual(self.client.post("/restaurants/reservations/placeA/new", data=data).status_code, 302)
        with self.app.app_context():
            reservation = Reservation.query.one()
            self.assertEqual(reservation.status, "pending")
            reservation_id = reservation.id
        page = self.client.get("/users/").get_data(as_text=True)
        self.assertIn("承認待ち（未確定）", page)
        self.assertIn("店舗A", page)

        self.login("other@example.com")
        self.assertNotIn("店舗A", self.client.get("/users/").get_data(as_text=True))
        self.assertEqual(self.client.get("/restaurants/reservations").status_code, 403)

        self.login("shop2@example.com")
        self.assertNotIn("ヤマダ タロウ", self.client.get("/restaurants/reservations").get_data(as_text=True))
        with self.client.session_transaction() as session:
            session["reservation_csrf"] = "valid-token"
        self.assertEqual(self.client.post(
            f"/restaurants/reservations/{reservation_id}/status",
            data={"csrf_token": "valid-token", "action": "confirm"},
        ).status_code, 404)

        self.login("shop@example.com")
        token = self.management_token()
        self.assertEqual(self.client.post(
            f"/restaurants/reservations/{reservation_id}/status",
            data={"action": "confirm"},
        ).status_code, 400)
        self.assertEqual(self.client.post(
            f"/restaurants/reservations/{reservation_id}/status",
            data={"csrf_token": token, "action": "confirm"},
        ).status_code, 302)
        self.login("user@example.com")
        self.assertIn("予約確定", self.client.get("/users/").get_data(as_text=True))
        self.login("shop@example.com")
        token = self.management_token()
        self.assertEqual(self.client.post(
            f"/restaurants/reservations/{reservation_id}/status",
            data={"csrf_token": token, "action": "cancel"},
        ).status_code, 302)
        self.assertEqual(self.client.post(
            f"/restaurants/reservations/{reservation_id}/status",
            data={"csrf_token": token, "action": "confirm"},
        ).status_code, 404)
        self.login("user@example.com")
        self.assertIn("店舗によりキャンセル", self.client.get("/users/").get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(Reservation.query.one().status, "cancelled")
        restarted_app = create_app(self.config)
        restarted_client = restarted_app.test_client()
        with restarted_client.session_transaction() as session:
            session["email"] = "user@example.com"
        self.assertIn("店舗によりキャンセル", restarted_client.get("/users/").get_data(as_text=True))
        with restarted_app.app_context():
            db.session.remove()
            db.engine.dispose()

    def test_validation_csrf_and_lost_link(self):
        self.login("user@example.com")
        data = self.form_data()
        for field, value in (
            ("name", "山田"),
            ("guests", "21"),
            ("datetime", "2020-01-01T12:00"),
            ("csrf_token", "不正"),
        ):
            response = self.client.post(
                "/restaurants/reservations/placeA/new",
                data={**data, field: value},
            )
            self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            Account.query.filter_by(email="shop@example.com").one().place_id = None
            db.session.commit()
        self.assertEqual(self.client.post("/restaurants/reservations/placeA/new", data=data).status_code, 404)
        with self.app.app_context():
            self.assertEqual(Reservation.query.count(), 0)

    def test_old_reservation_cannot_be_approved(self):
        self.login("user@example.com")
        data = self.form_data()
        self.client.post("/restaurants/reservations/placeA/new", data=data)
        with self.app.app_context():
            reservation = Reservation.query.one()
            reservation.reserved_at = datetime.now() - timedelta(days=1)
            reservation_id = reservation.id
            db.session.commit()
        self.login("shop@example.com")
        token = self.management_token()
        self.assertEqual(self.client.post(
            f"/restaurants/reservations/{reservation_id}/status",
            data={"csrf_token": token, "action": "confirm"},
        ).status_code, 404)
        with self.app.app_context():
            self.assertEqual(Reservation.query.one().status, "pending")


class ReservationMigrationTests(unittest.TestCase):
    def test_existing_reservations_are_preserved_by_location_upgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "migration.sqlite"
            app = create_app({
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///" + path.as_posix(),
            })
            with app.app_context():
                upgrade(revision="91d2e3f4a5b6")
                db.session.add_all([
                    Account(email="user@example.com", name="利用者", account_type="user", password_hash="x"),
                    Account(email="shop@example.com", name="店舗", account_type="restaurant", password_hash="x"),
                ])
                db.session.flush()
                user = Account.query.filter_by(email="user@example.com").one()
                shop = Account.query.filter_by(email="shop@example.com").one()
                db.session.execute(db.text(
                    "INSERT INTO reservation (user_id, restaurant_id, name, guests, reserved_at, "
                    "status, submission_key, created_at) VALUES (:user, :shop, :name, 2, "
                    ":reserved_at, 'pending', :submission_key, :created_at)"
                ), {
                    "user": user.id, "shop": shop.id, "name": "ヤマダ",
                    "reserved_at": datetime(2030, 1, 1), "created_at": datetime(2026, 1, 1),
                    "submission_key": "a" * 64,
                })
                db.session.commit()
                upgrade()
                reservation = Reservation.query.one()
                self.assertEqual(reservation.name, "ヤマダ")
                self.assertTrue(reservation.is_demo)
                self.assertEqual(reservation.restaurant_id, shop.id)
                db.session.remove()
                db.engine.dispose()

    def test_upgrade_preserves_accounts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "migration.sqlite"
            app = create_app({
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///" + path.as_posix(),
            })
            with app.app_context():
                upgrade(revision="8f1b6c2d3e40")
                db.session.add(Account(email="shop@example.com", name="店舗", account_type="restaurant", password_hash="x", place_id="placeA"))
                db.session.commit()
                upgrade()
                self.assertEqual(Account.query.one().place_id, "placeA")
                self.assertEqual(Reservation.query.count(), 0)
                db.session.remove()
                db.engine.dispose()
