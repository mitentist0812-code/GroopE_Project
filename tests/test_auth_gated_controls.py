import unittest

from apps import create_app


class AuthGatedControlsTests(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.config["TESTING"] = True
        self.client = app.test_client()

    def login_session(self, account_type="user"):
        with self.client.session_transaction() as session:
            session["email"] = "test@example.com"
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
        self.assertIn('class="button button-primary reservation-button auth-disabled-control"', restaurant)
        self.assertIn('class="favorite-button active" id="favoriteButton" disabled', restaurant)

        reservation = self.client.get("/restaurants/reservations/new").get_data(as_text=True)
        self.assertIn('class="reservation-submit-button" disabled', reservation)

        recipe_detail = self.client.get("/recipes/detail").get_data(as_text=True)
        self.assertIn('id="favoriteButton" aria-pressed="false" disabled', recipe_detail)
        self.assertIn('id="reviewButton" disabled', recipe_detail)

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
        self.assertIn('href="/restaurants/reservations/new" class="button button-primary reservation-button"', restaurant)

        reservation = self.client.get("/restaurants/reservations/new").get_data(as_text=True)
        self.assertRegex(reservation, r'class="reservation-submit-button"\s*>')

        recipe_detail = self.client.get("/recipes/detail").get_data(as_text=True)
        self.assertRegex(recipe_detail, r'id="favoriteButton" aria-pressed="false"\s*>')
        self.assertRegex(recipe_detail, r'id="reviewButton"\s*>')


if __name__ == "__main__":
    unittest.main()
