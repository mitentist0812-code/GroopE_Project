import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apps import create_app
from apps.allergens import (
    AllergenModelUnavailable,
    _possible_allergens,
    analyze_allergens,
    matching_user_allergens,
)
from apps.auth.models import Account, AccountPreference
from apps.extensions import db
from apps.recipes.models import Recipe_list
from apps.restaurants.models import RestaurantMenu


PLACE = {
    "name": "アレルゲン確認店",
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


class AllergenTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "allergens.sqlite"
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + database_path.as_posix(),
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            self.restaurant = Account(
                email="restaurant@example.com",
                password_hash="unused",
                account_type="restaurant",
                name="アレルゲン確認店",
                place_id="place123",
            )
            self.other_restaurant = Account(
                email="other@example.com",
                password_hash="unused",
                account_type="restaurant",
                name="メニュー未登録店",
                place_id="place456",
            )
            self.user = Account(
                email="user@example.com",
                password_hash="unused",
                account_type="user",
                name="アレルギー利用者",
            )
            self.recipe = Recipe_list(
                recipe_name="たまごケーキ",
                ingredients="卵 1個\n小麦粉 50g",
                description="スポンジを焼く",
            )
            db.session.add_all([
                self.restaurant,
                self.other_restaurant,
                self.user,
                self.recipe,
            ])
            db.session.flush()
            db.session.add_all([
                RestaurantMenu(
                    restaurant_id=self.restaurant.id,
                    name="だし巻き定食",
                    price=800,
                    calories=600,
                ),
                RestaurantMenu(
                    restaurant_id=self.restaurant.id,
                    name="野菜カレー",
                    price=900,
                    calories=700,
                ),
            ])
            db.session.commit()
            self.recipe_id = self.recipe.id
            self.user_id = self.user.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def test_only_scores_at_or_above_threshold_are_displayed(self):
        self.assertEqual(
            _possible_allergens(
                ["eggs", "gluten", "milk"],
                [0.49, 0.5, 0.9],
            ),
            ["小麦・グルテン", "乳"],
        )

    def test_user_allergies_match_supported_model_candidates(self):
        self.assertEqual(
            matching_user_allergens(
                ["卵", "エビ", "そば"],
                ["卵", "甲殻類"],
            ),
            ["卵", "エビ"],
        )
        self.assertEqual(matching_user_allergens(["そば"], ["小麦・グルテン"]), [])

    def test_empty_texts_skip_model_loading(self):
        with patch("apps.allergens._load_model") as load_model:
            self.assertEqual(analyze_allergens(["", "  "]), [[], []])
        load_model.assert_not_called()

    def test_recipe_detail_warns_for_model_candidates(self):
        with patch(
            "apps.recipes.views.analyze_allergens",
            return_value=[["卵", "小麦・グルテン"]],
        ) as analyze:
            response = self.client.get(f"/recipes/{self.recipe_id}")

        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("次のアレルゲンが含まれる可能性があります", text)
        self.assertIn("小麦・グルテン", text)
        self.assertIn("必ず提供者に確認してください", text)
        analyze.assert_called_once_with([
            "たまごケーキ\n卵 1個\n小麦粉 50g\nスポンジを焼く",
        ])

    @patch("apps.restaurants.views.place_details", return_value=PLACE)
    def test_linked_store_menus_are_checked_and_candidates_displayed(
        self,
        details,
    ):
        with patch(
            "apps.restaurants.views.analyze_allergens",
            return_value=[["卵"], []],
        ) as analyze:
            response = self.client.get("/restaurants/detail/place123")

        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("だし巻き定食", text)
        self.assertIn("卵", text)
        self.assertNotIn("野菜カレー", text)
        self.assertIn("料理名だけからの推定です", text)
        details.assert_called_once_with("place123")
        analyze.assert_called_once_with(["だし巻き定食", "野菜カレー"])

    @patch("apps.restaurants.views.place_details", return_value=PLACE)
    def test_store_detail_warns_when_menu_matches_saved_allergy(self, details):
        with self.app.app_context():
            db.session.add(AccountPreference(
                account_id=self.user_id,
                allergies=["卵"],
            ))
            db.session.commit()
        with self.client.session_transaction() as session:
            session["email"] = self.user.email

        with patch(
            "apps.restaurants.views.analyze_allergens",
            return_value=[["卵"], []],
        ):
            response = self.client.get("/restaurants/detail/place123")

        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("設定中のアレルギー（卵）に該当する可能性のあるメニューがあります", text)
        self.assertIn("だし巻き定食", text)
        self.assertNotIn("野菜カレー</strong>：", text)
        details.assert_called_once_with("place123")

    @patch("apps.restaurants.views.place_details", return_value=PLACE)
    def test_store_without_registered_menus_is_not_reported_as_clear(
        self,
        details,
    ):
        with patch("apps.restaurants.views.analyze_allergens") as analyze:
            response = self.client.get("/restaurants/detail/place456")

        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("登録メニュー情報がないため", text)
        self.assertIn("店舗に直接お問い合わせください", text)
        analyze.assert_not_called()

    def test_model_unavailable_is_reported_instead_of_claiming_no_allergens(
        self,
    ):
        with patch(
            "apps.recipes.views.analyze_allergens",
            side_effect=AllergenModelUnavailable("model unavailable"),
        ):
            response = self.client.get(f"/recipes/{self.recipe_id}")

        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("アレルゲン候補を判定できませんでした", text)
        self.assertNotIn("モデルはアレルゲン候補を検出しませんでした", text)


if __name__ == "__main__":
    unittest.main()
