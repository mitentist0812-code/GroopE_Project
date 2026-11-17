import tempfile
import unittest
from pathlib import Path

from apps import create_app
from apps.auth.models import Account
from apps.extensions import db
from apps.restaurants.models import RestaurantMenu


class RestaurantMenuTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "menus.sqlite"
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + database_path.as_posix(),
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            self.restaurant = Account(
                email="restaurant@example.com",
                password_hash="unused",
                account_type="restaurant",
                name="Test Restaurant",
            )
            self.other_restaurant = Account(
                email="other@example.com",
                password_hash="unused",
                account_type="restaurant",
                name="Other Restaurant",
            )
            self.user = Account(
                email="user@example.com",
                password_hash="unused",
                account_type="user",
                name="Test User",
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
        with self.client.session_transaction() as session:
            session["email"] = email
            session["account_type"] = (
                "restaurant" if email != self.user_email else "user"
            )

    def test_menu_crud_persists_and_is_scoped_to_the_restaurant(self):
        self.login_as(self.restaurant_email)
        created = self.client.post("/restaurants/api/menus", json={
            "menus": [{"name": " 日替わり定食 ", "price": 980, "calories": 650}],
        })
        self.assertEqual(created.status_code, 201)
        menu = created.get_json()["menus"][0]
        self.assertEqual(
            {
                key: menu[key]
                for key in ("name", "price", "calories")
            },
            {"name": "日替わり定食", "price": 980, "calories": 650},
        )

        listed = self.client.get("/restaurants/api/menus")
        self.assertEqual(listed.get_json()["menus"], [menu])
        self.assertEqual(
            self.client.delete(
                f"/restaurants/api/menus/{menu['id']}"
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get("/restaurants/api/menus").get_json()["menus"],
            [],
        )

        self.login_as(self.other_restaurant_email)
        self.assertEqual(
            self.client.get("/restaurants/api/menus").get_json()["menus"],
            [],
        )

    def test_menu_api_requires_a_restaurant_account(self):
        self.assertEqual(
            self.client.get("/restaurants/api/menus").status_code,
            401,
        )

        self.login_as(self.user_email)
        self.assertEqual(
            self.client.post("/restaurants/api/menus", json={
                "menus": [{"name": "定食", "price": 500, "calories": 600}],
            }).status_code,
            403,
        )

    def test_menu_management_uses_the_server_api(self):
        self.login_as(self.restaurant_email)
        response = self.client.get("/restaurants/menu")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("店舗アカウントに紐づけてサーバーに保存", page)
        self.assertIn('const menuItemsUrl = "/restaurants/api/menus";', page)
        self.assertNotIn("localStorage", page)

    def test_invalid_batch_is_rejected_without_saving_any_menu(self):
        self.login_as(self.restaurant_email)
        response = self.client.post("/restaurants/api/menus", json={
            "menus": [
                {"name": "有効な料理", "price": 500, "calories": 600},
                {"name": "不正な料理", "price": -1, "calories": 300},
            ],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("値段", response.get_json()["error"])
        self.assertEqual(
            self.client.get("/restaurants/api/menus").get_json()["menus"],
            [],
        )
        with self.app.app_context():
            self.assertEqual(RestaurantMenu.query.count(), 0)

    def test_restaurant_cannot_delete_another_restaurants_menu(self):
        with self.app.app_context():
            menu = RestaurantMenu(
                restaurant_id=self.restaurant.id,
                name="日替わり定食",
                price=980,
                calories=650,
            )
            db.session.add(menu)
            db.session.commit()
            menu_id = menu.id

        self.login_as(self.other_restaurant_email)
        self.assertEqual(
            self.client.delete(
                f"/restaurants/api/menus/{menu_id}"
            ).status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()
