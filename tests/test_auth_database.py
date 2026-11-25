import tempfile
import unittest
from pathlib import Path

from werkzeug.security import check_password_hash

from apps import create_app
from apps.auth.models import Account
from apps.extensions import db
from apps.recipes import models as recipe_models


class AuthDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "accounts.sqlite"
        self.app_config = {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + database_path.as_posix(),
        }
        self.apps = []
        self.app = self.make_app()
        self.client = self.app.test_client()

    def tearDown(self):
        for app in self.apps:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        self.temp_dir.cleanup()

    def make_app(self):
        app = create_app(self.app_config)
        self.apps.append(app)
        with app.app_context():
            db.create_all()
        return app

    def test_auth_and_recipes_share_the_app_database_extension(self):
        self.assertIs(recipe_models.db, db)
        self.assertIs(Account.metadata, db.metadata)

    def test_auth_headers_do_not_render_a_second_brand_mark(self):
        for path in ("/auth/login", "/auth/signup", "/auth/signup/restaurant"):
            with self.subTest(path=path):
                response = self.client.get(path)
                header = response.get_data(as_text=True).split('<header class="brand">', 1)[1].split("</header>", 1)[0]
                self.assertIn('<h1><a href="/auth/login">一飯一会</a></h1>', header)
                self.assertNotIn('class="brand-mark"', header)

    def test_user_account_persists_and_can_log_in_after_app_restart(self):
        response = self.client.post("/auth/signup", data={
            "user-name": "Test User",
            "email": "user@example.com",
            "password": "password123",
            "password-confirm": "password123",
        })
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            account = Account.query.filter_by(email="user@example.com").one()
            self.assertEqual(account.account_type, "user")
            self.assertTrue(check_password_hash(account.password_hash, "password123"))
            self.assertNotEqual(account.password_hash, "password123")

        restarted_client = self.make_app().test_client()
        login = restarted_client.post("/auth/login", data={
            "email": "user@example.com",
            "password": "password123",
        })
        self.assertEqual(login.status_code, 302)
        with restarted_client.session_transaction() as session:
            self.assertEqual(session["account_type"], "user")
            self.assertEqual(session["name"], "Test User")
        header = restarted_client.get("/").get_data(as_text=True)
        self.assertIn('class="account-name">Test User</span>', header)

    def test_restaurant_account_persists_with_its_role(self):
        response = self.client.post("/auth/signup/restaurant", data={
            "restaurant_name": "Test Restaurant",
            "email": "restaurant@example.com",
            "password": "password123",
            "password_confirm": "password123",
            "address": "Tokyo",
            "phone": "03-1234-5678",
        })
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            account = Account.query.filter_by(email="restaurant@example.com").one()
            self.assertEqual(account.account_type, "restaurant")
            self.assertEqual(account.address, "Tokyo")
            self.assertEqual(account.phone, "03-1234-5678")

        login = self.client.post("/auth/login", data={
            "email": "restaurant@example.com",
            "password": "password123",
        })
        self.assertEqual(login.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertEqual(session["account_type"], "restaurant")
            self.assertEqual(session["name"], "Test Restaurant")

    def test_email_is_unique_across_account_types(self):
        self.client.post("/auth/signup", data={
            "user-name": "Test User",
            "email": "shared@example.com",
            "password": "password123",
            "password-confirm": "password123",
        })
        response = self.client.post("/auth/signup/restaurant", data={
            "restaurant_name": "Test Restaurant",
            "email": "shared@example.com",
            "password": "password123",
            "password_confirm": "password123",
            "address": "Tokyo",
            "phone": "",
        })

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(Account.query.filter_by(email="shared@example.com").count(), 1)


if __name__ == "__main__":
    unittest.main()
