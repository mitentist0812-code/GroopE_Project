import unittest

from apps import create_app
from apps.auth.models import Account
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
        self.assertIn('placeholder="user@example.com"', settings_text)
        self.assertEqual(settings.headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
