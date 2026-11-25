import re
import unittest

from apps import create_app
from apps.auth.models import Account, AccountPreference
from apps.extensions import db
from apps.recipes.models import Recipe_list
from apps.review_models import ContentReview


class MypageTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            self.user = Account(
                email="user@example.com",
                password_hash="unused",
                account_type="user",
                name="ページ利用者",
            )
            self.other_user = Account(
                email="other@example.com",
                password_hash="unused",
                account_type="user",
                name="別の利用者",
            )
            self.restaurant = Account(
                email="restaurant@example.com",
                password_hash="unused",
                account_type="restaurant",
                name="店舗アカウント",
            )
            self.recipe = Recipe_list(
                recipe_name="自分のカレー",
                ingredients="玉ねぎ",
                description="煮る",
            )
            self.other_recipe = Recipe_list(
                recipe_name="他人のレシピ",
                ingredients="にんじん",
                description="切る",
            )
            db.session.add_all([
                self.user,
                self.other_user,
                self.restaurant,
                self.recipe,
                self.other_recipe,
            ])
            db.session.flush()
            self.recipe.account_id = self.user.id
            self.other_recipe.account_id = self.other_user.id
            db.session.add_all([
                ContentReview(
                    account_id=self.user.id,
                    recipe_id=self.recipe.id,
                    rating=5,
                    comment="作りやすかったです。",
                ),
                ContentReview(
                    account_id=self.user.id,
                    place_id="place-123",
                    rating=4,
                    comment="また行きたいです。",
                ),
                ContentReview(
                    account_id=self.other_user.id,
                    recipe_id=self.other_recipe.id,
                    rating=1,
                    comment="他人のレビュー",
                ),
            ])
            db.session.commit()
            self.user_email = self.user.email
            self.restaurant_email = self.restaurant.email

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def login_as(self, email):
        with self.client.session_transaction() as session:
            session["email"] = email

    def test_requires_a_logged_in_user_account(self):
        response = self.client.get("/users/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/auth/login")
        self.assertEqual(self.client.get("/users/settings").status_code, 302)

        self.login_as(self.restaurant_email)
        response = self.client.get("/users/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/restaurants/")

    def test_displays_account_details_and_only_owned_recipes(self):
        self.login_as(self.user_email)
        response = self.client.get("/users/")
        text = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("ページ利用者", text)
        self.assertIn("user@example.com", text)
        self.assertIn("お気に入り", text)
        self.assertIn("閲覧履歴", text)
        self.assertIn("自分のカレー", text)
        self.assertNotIn("他人のレシピ", text)
        self.assertNotIn("他人のレビュー", text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

        settings = self.client.get("/users/settings")
        settings_text = settings.get_data(as_text=True)
        self.assertEqual(settings.status_code, 200)
        self.assertIn('value="ページ利用者"', settings_text)
        self.assertIn('value="user@example.com"', settings_text)
        self.assertEqual(settings.headers["Cache-Control"], "no-store")

    def test_saves_available_settings_and_preserves_unavailable_preferences(self):
        with self.app.app_context():
            account = Account.query.filter_by(email=self.user_email).one()
            db.session.add(AccountPreference(
                account_id=account.id,
                favorite_foods="カレー、寿司",
                disliked_foods="納豆",
                religion="イスラム教",
                use_location=False,
                health_mode=True,
            ))
            db.session.commit()
        self.login_as(self.user_email)
        settings = self.client.get("/users/settings")
        token = re.search(
            r'name="csrf_token" value="([^"]+)"',
            settings.get_data(as_text=True),
        ).group(1)

        response = self.client.post("/users/settings", data={
            "csrf_token": token,
            "name": "更新後の名前",
            "email": "updated@example.com",
            "allergies": ["卵", "エビ"],
            "autofill_email": "1",
        })

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            account = Account.query.filter_by(email="updated@example.com").one()
            preferences = AccountPreference.query.filter_by(
                account_id=account.id,
            ).one()
            self.assertEqual(account.name, "更新後の名前")
            self.assertEqual(preferences.favorite_foods, "カレー、寿司")
            self.assertEqual(preferences.disliked_foods, "納豆")
            self.assertEqual(preferences.allergies, ["卵", "エビ"])
            self.assertEqual(preferences.religion, "イスラム教")
            self.assertFalse(preferences.use_location)
            self.assertTrue(preferences.health_mode)
            self.assertTrue(preferences.autofill_email)

        with self.client.session_transaction() as session:
            self.assertEqual(session["email"], "updated@example.com")
            self.assertEqual(session["name"], "更新後の名前")

        settings = self.client.get("/users/settings")
        text = settings.get_data(as_text=True)
        self.assertIn('value="updated@example.com"', text)
        self.assertIn('value="卵" checked', text)
        self.assertIn('value="エビ" checked', text)
        self.assertIn('value="イスラム教" selected', text)
        self.assertIn('id="remember-login-email"', text)
        self.assertIn('name="autofill_email" value="1" checked', text)
        for field in ("use_location", "health_mode", "favorite_foods", "disliked_foods", "religion"):
            self.assertRegex(text, rf'<(?:input|select)\b[^>]*name="{field}"[^>]*\bdisabled\b')
        self.assertIn("未実装", text)
        self.assertNotRegex(text, r'<input\b[^>]*name="allergies"[^>]*\bdisabled\b')

        token = re.search(
            r'name="csrf_token" value="([^"]+)"',
            text,
        ).group(1)
        response = self.client.post("/users/settings", data={
            "csrf_token": token,
            "name": "更新後の名前",
            "email": "updated@example.com",
            "allergies": ["卵", "エビ"],
        })
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            account = Account.query.filter_by(email="updated@example.com").one()
            preferences = AccountPreference.query.filter_by(
                account_id=account.id,
            ).one()
            self.assertFalse(preferences.autofill_email)
        text = self.client.get("/users/settings").get_data(as_text=True)
        self.assertNotIn('name="autofill_email" value="1" checked', text)

    def test_unavailable_preferences_cannot_be_submitted(self):
        self.login_as(self.user_email)
        text = self.client.get("/users/settings").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', text).group(1)
        for field in ("use_location", "health_mode", "favorite_foods", "disliked_foods", "religion"):
            with self.subTest(field=field):
                response = self.client.post("/users/settings", data={
                    "csrf_token": token,
                    "name": "ページ利用者",
                    "email": self.user_email,
                    field: "1",
                })
                self.assertEqual(response.status_code, 400)
                self.assertIn("未実装の設定は変更できません", response.get_data(as_text=True))

    def test_settings_reject_invalid_values_and_invalid_csrf(self):
        self.login_as(self.user_email)
        settings = self.client.get("/users/settings")
        token = re.search(
            r'name="csrf_token" value="([^"]+)"',
            settings.get_data(as_text=True),
        ).group(1)
        data = {
            "csrf_token": token,
            "name": "変更しない",
            "email": "user@example.com",
            "allergies": "想定外",
        }

        self.assertEqual(
            self.client.post("/users/settings", data={**data, "csrf_token": "bad"}).status_code,
            400,
        )
        response = self.client.post("/users/settings", data=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("アレルギーの選択内容", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(
                Account.query.filter_by(email=self.user_email).one().name,
                "ページ利用者",
            )

    def test_settings_reject_an_email_used_by_another_account(self):
        self.login_as(self.user_email)
        settings = self.client.get("/users/settings")
        token = re.search(
            r'name="csrf_token" value="([^"]+)"',
            settings.get_data(as_text=True),
        ).group(1)
        response = self.client.post("/users/settings", data={
            "csrf_token": token,
            "name": "変更しない",
            "email": self.restaurant_email,
        })

        self.assertEqual(response.status_code, 409)
        self.assertIn("既に登録", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(
                Account.query.filter_by(email=self.user_email).one().name,
                "ページ利用者",
            )

    def test_login_page_loads_the_opt_in_email_autofill_script(self):
        response = self.client.get("/auth/login")
        text = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('autocomplete="email"', text)
        self.assertIn("login-email-autofill.js", text)


if __name__ == "__main__":
    unittest.main()
