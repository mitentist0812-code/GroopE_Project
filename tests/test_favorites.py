import unittest
from unittest.mock import patch

from apps import create_app
from apps.auth.models import Account
from apps.extensions import db
from apps.recipes.models import RecipeFavorite, Recipe_list
from apps.restaurants.models import PlaceFavorite


class FavoritesTests(unittest.TestCase):
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
                name="ユーザー",
                account_type="user",
                password_hash="unused",
            )
            self.other_user = Account(
                email="other@example.com",
                name="別のユーザー",
                account_type="user",
                password_hash="unused",
            )
            self.restaurant = Account(
                email="restaurant@example.com",
                name="店舗",
                account_type="restaurant",
                password_hash="unused",
            )
            self.recipe = Recipe_list(
                recipe_name="野菜カレー",
                ingredients="玉ねぎ",
                description="煮る",
            )
            db.session.add_all([
                self.user,
                self.other_user,
                self.restaurant,
                self.recipe,
            ])
            db.session.commit()
            self.recipe_id = self.recipe.id
            self.user_email = self.user.email
            self.other_user_email = self.other_user.email
            self.restaurant_email = self.restaurant.email

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def login_as(self, email):
        with self.client.session_transaction() as session:
            session["email"] = email

    def test_recipe_favorite_persists_per_account_and_can_be_removed(self):
        self.login_as(self.user_email)
        response = self.client.post(
            f"/users/favorites/recipes/{self.recipe_id}",
            data={"action": "add"},
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(RecipeFavorite.query.count(), 1)

        with patch("apps.recipes.views.analyze_allergens", return_value=[[]]):
            detail = self.client.get(f"/recipes/{self.recipe_id}").get_data(as_text=True)
        self.assertIn('class="favorite-button active"', detail)
        self.assertIn("♥ お気に入り登録済み", detail)

        favorites = self.client.get("/users/favorites")
        self.assertEqual(favorites.status_code, 200)
        self.assertIn("野菜カレー", favorites.get_data(as_text=True))
        self.assertEqual(favorites.headers["Cache-Control"], "no-store")

        self.login_as(self.other_user_email)
        other_favorites = self.client.get("/users/favorites").get_data(as_text=True)
        self.assertNotIn("野菜カレー", other_favorites)

        self.login_as(self.user_email)
        response = self.client.post(
            f"/users/favorites/recipes/{self.recipe_id}",
            data={"action": "remove", "return_to": "favorites"},
        )
        self.assertEqual(response.headers["Location"], "/users/favorites")
        with self.app.app_context():
            self.assertEqual(RecipeFavorite.query.count(), 0)

    def test_place_favorite_uses_place_id_and_can_be_removed_from_list(self):
        self.login_as(self.user_email)
        response = self.client.post(
            "/users/favorites/places/place123",
            data={"action": "add"},
        )
        self.assertEqual(response.headers["Location"], "/restaurants/detail/place123")
        with self.app.app_context():
            self.assertEqual(PlaceFavorite.query.count(), 1)

        with patch("apps.users.views.place_details", return_value={
            "name": "テスト店舗",
            "address": "東京都千代田区",
        }):
            favorites = self.client.get("/users/favorites")
        self.assertEqual(favorites.status_code, 200)
        self.assertIn("テスト店舗", favorites.get_data(as_text=True))
        self.assertIn("東京都千代田区", favorites.get_data(as_text=True))

        response = self.client.post(
            "/users/favorites/places/place123",
            data={"action": "remove", "return_to": "favorites"},
        )
        self.assertEqual(response.headers["Location"], "/users/favorites")
        with self.app.app_context():
            self.assertEqual(PlaceFavorite.query.count(), 0)

    def test_favorite_routes_require_user_account_and_validate_place_id(self):
        self.assertEqual(
            self.client.post(
                f"/users/favorites/recipes/{self.recipe_id}",
                data={"action": "add"},
            ).status_code,
            302,
        )
        self.login_as(self.restaurant_email)
        response = self.client.get("/users/favorites")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/restaurants/")

        response = self.client.post(
            "/users/favorites/places/bad%20place",
            data={"action": "add"},
        )
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            self.assertEqual(RecipeFavorite.query.count(), 0)
            self.assertEqual(PlaceFavorite.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
