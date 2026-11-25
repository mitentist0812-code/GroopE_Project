import re
import unittest
from unittest.mock import patch

from apps import create_app
from apps.auth.models import Account
from apps.extensions import db
from apps.recipes.models import Recipe_list


class AuthGatedControlsTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            account = Account(
                email="test@example.com",
                name="テストユーザー",
                account_type="user",
                password_hash="unused",
            )
            restaurant_account = Account(
                email="restaurant@example.com",
                name="テスト店舗",
                account_type="restaurant",
                password_hash="unused",
            )
            db.session.add(account)
            db.session.add(restaurant_account)
            db.session.commit()
            
            recipe = Recipe_list(
                recipe_name="テストレシピ",
                ingredients="テスト材料",
                description="テスト説明",
                steps=["ステップ1"],
                account_id=account.id,
            )
            db.session.add(recipe)
            db.session.commit()
            self.recipe_id = recipe.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def login_session(self, account_type="user"):
        with self.client.session_transaction() as session:
            session["email"] = "restaurant@example.com" if account_type == "restaurant" else "test@example.com"
            session["account_type"] = account_type

    def test_account_actions_match_login_and_account_type(self):
        anonymous_home = self.client.get("/").get_data(as_text=True)
        self.assertIn('href="/auth/login" class="account-link">ログイン', anonymous_home)
        self.assertIn('href="/auth/signup" class="account-link">新規登録', anonymous_home)
        self.assertNotIn('href="/auth/logout"', anonymous_home)
        self.assertNotIn("mode-toggle", anonymous_home)
        self.assertNotIn('href="/users/"', anonymous_home)
        self.assertNotIn('href="/restaurants/" class="account-link"', anonymous_home)

        self.login_session()
        user_home = self.client.get("/").get_data(as_text=True)
        self.assertNotIn('class="account-link">マイページ', user_home)
        self.assertRegex(user_home, r'href="/users/"\s*>マイページ')
        self.assertIn('href="/auth/logout" class="logout">ログアウト', user_home)
        self.assertNotIn('href="/restaurants/" class="account-link"', user_home)
        self.assertNotIn("mode-toggle", user_home)

        self.login_session(account_type="restaurant")
        restaurant_home = self.client.get("/").get_data(as_text=True)
        self.assertIn('href="/restaurants/" class="account-link">店舗管理', restaurant_home)
        self.assertIn('href="/auth/logout" class="logout">ログアウト', restaurant_home)
        self.assertNotIn('href="/users/" class="account-link"', restaurant_home)
        self.assertNotIn("mode-toggle", restaurant_home)

    def test_logout_requires_confirmation_and_preserves_cancelled_session(self):
        for account_type in ("user", "restaurant"):
            with self.subTest(account_type=account_type):
                self.login_session(account_type)
                home = self.client.get("/").get_data(as_text=True)
                form = home.split('<form id="logout-form"', 1)[1].split("</form>", 1)[0]
                self.assertIn('action="/auth/logout" method="post"', form)
                token = re.search(r'name="csrf_token" value="([^"]+)"', form).group(1)
                response = self.client.get("/auth/logout")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                text = response.get_data(as_text=True)
                self.assertIn("ログアウトしますか？", text)
                self.assertIn(">いいえ</a>", text)
                self.assertIn(">はい</button>", text)
                self.assertIn(f'name="csrf_token" value="{token}"', text)
                self.client.get("/")
                with self.client.session_transaction() as session:
                    self.assertEqual(session["account_type"], account_type)
                self.assertEqual(self.client.post("/auth/logout", data={"csrf_token": "不正"}).status_code, 400)
                with self.client.session_transaction() as session:
                    self.assertEqual(session["account_type"], account_type)
                response = self.client.post("/auth/logout", data={"csrf_token": token})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Location"], "/auth/login")
                with self.client.session_transaction() as session:
                    self.assertNotIn("email", session)

    def test_controls_are_disabled_for_anonymous_visitors(self):
        home = self.client.get("/").get_data(as_text=True)
        self.assertIn('class="recipe-post-link auth-disabled-control"', home)
        self.assertIn('class="favorite-link auth-disabled-control"', home)

        recipe_post = self.client.get("/recipes/post").get_data(as_text=True)
        self.assertIn('class="submit-button" disabled', recipe_post)

        calorie = self.client.get("/nutrition/calorie").get_data(as_text=True)
        self.assertIn('data-authenticated="false"', calorie)
        self.assertIn("カロリー計算を利用するにはログインしてください。", calorie)

        restaurant = self.client.get("/restaurants/detail").get_data(as_text=True)
        self.assertIn("予約対象外（サンプル）", restaurant)
        self.assertIn('class="favorite-button" id="favoriteButton"', restaurant)
        self.assertIn('title="ログインすると利用できます"', restaurant)

        reservation = self.client.get("/restaurants/reservations/place123/new")
        self.assertEqual(reservation.headers["Location"], "/auth/login")

        recipe_detail = self.client.get(f"/recipes/{self.recipe_id}").get_data(as_text=True)
        self.assertIn('class="recipe-detail"', recipe_detail)

    def test_controls_remain_available_for_authenticated_visitors(self):
        self.login_session()

        home = self.client.get("/").get_data(as_text=True)
        self.assertIn('href="/recipes/post" class="recipe-post-link"', home)
        self.assertNotIn("auth-disabled-control", home)

        recipe_post = self.client.get("/recipes/post").get_data(as_text=True)
        self.assertRegex(recipe_post, r'class="submit-button"\s*>')

        calorie = self.client.get("/nutrition/calorie").get_data(as_text=True)
        self.assertIn('data-authenticated="true"', calorie)
        self.assertNotIn("カロリー計算を利用するにはログインしてください。", calorie)

        restaurant = self.client.get("/restaurants/detail").get_data(as_text=True)
        self.assertIn("予約対象外（サンプル）", restaurant)

        recipe_detail = self.client.get(f"/recipes/{self.recipe_id}").get_data(as_text=True)
        self.assertIn('class="recipe-detail"', recipe_detail)
        self.assertIn('class="review-form"', recipe_detail)

    def test_restaurant_account_consumer_controls_are_disabled(self):
        self.login_session(account_type="restaurant")
        home = self.client.get("/").get_data(as_text=True)
        self.assertIn('class="favorite-link auth-disabled-control"', home)
        self.assertIn('class="recipe-post-link auth-disabled-control"', home)
        self.assertIn('data-tab="home-recipes" disabled', home)
        self.assertIn('class="recipe-card-image auth-disabled-control"', home)
        self.assertNotIn(f'href="/recipes/{self.recipe_id}"', home)
        self.assertIn('id="recommend" class="search-panel active"', home)
        self.assertIn('href="/restaurants/" class="account-link">店舗管理', home)
        self.assertNotIn('href="/nutrition/calorie"', home)
        self.assertNotIn('href="/recipes/post"', home)

        for method in (self.client.get, self.client.post):
            self.assertEqual(method("/recipe-results", query_string={"keyword": "テスト"}).status_code, 403)
        recipe_post = self.client.get("/recipes/post").get_data(as_text=True)
        self.assertIn('class="submit-button" disabled', recipe_post)
        self.assertEqual(self.client.post("/recipes/post").status_code, 403)
        with self.app.app_context():
            self.assertEqual(Recipe_list.query.count(), 1)

        calorie = self.client.get("/nutrition/calorie").get_data(as_text=True)
        self.assertIn('data-authenticated="false"', calorie)
        for method, path in ((self.client.get, "/nutrition/foods"), (self.client.post, "/nutrition/calorie/analyze")):
            response = method(path)
            self.assertEqual(response.status_code, 403)
            self.assertIn("店舗アカウント", response.json["error"])

        for path in ("/restaurants/detail", f"/recipes/{self.recipe_id}"):
            detail = self.client.get(path).get_data(as_text=True)
            self.assertIn('class="review-button" disabled', detail)
            self.assertIn("店舗アカウントではレビューを投稿できません。", detail)
            self.assertIn('disabled title="店舗アカウントでは利用できません"', detail)
            self.assertNotIn('class="review-form"', detail)

    @patch("apps.home.views.search_places")
    def test_restaurant_search_keeps_place_claim_available(self, search):
        self.login_session(account_type="restaurant")
        search.return_value = [{
            "id": "p1", "name": "店舗", "address": "東京", "distance": 10,
            "distance_exact": 10, "rating": None, "price": "不明", "url": "", "attributions": [],
        }]
        response = self.client.get("/results", query_string={
            "keyword": "店舗", "latitude": "35.68", "longitude": "139.76",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("この店舗をアカウントに連携", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
