import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apps import create_app
from apps.auth.models import Account
from apps.extensions import db
from apps.recipes.models import Recipe_list
from apps.review_models import ContentReview


PLACE = {
    "name": "レビュー対象店",
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


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "reviews.sqlite"
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + database_path.as_posix(),
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            self.user = Account(
                email="user@example.com",
                password_hash="unused",
                account_type="user",
                name="テストユーザー",
            )
            self.other_user = Account(
                email="other@example.com",
                password_hash="unused",
                account_type="user",
                name="別のユーザー",
            )
            self.restaurant = Account(
                email="restaurant@example.com",
                password_hash="unused",
                account_type="restaurant",
                name="店舗アカウント",
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
        self.temp_dir.cleanup()

    def login_as(self, email):
        with self.client.session_transaction() as session:
            session["email"] = email

    @patch("apps.recipes.views.analyze_allergens", return_value=[[]])
    def test_recipe_rating_is_selected_with_clickable_stars(self, analyze):
        self.login_as(self.user_email)
        url = f"/recipes/{self.recipe_id}"
        initial = self.client.get(url).get_data(as_text=True)
        self.assertRegex(
            initial,
            re.compile(
                r'(?s)<input\s+class="review-star-input"\s+'
                r'id="reviewRating4"\s+type="radio"\s+name="rating"\s+'
                r'value="4"\s+aria-label="4つ星"\s+required\s*>'
            ),
        )
        self.assertIn(
            'label class="review-star" for="reviewRating4"',
            initial,
        )

        self.client.post(
            f"{url}/reviews",
            data={"rating": "4", "comment": "星をクリックした評価"},
        )
        updated = self.client.get(url).get_data(as_text=True)
        self.assertRegex(
            updated,
            re.compile(
                r'(?s)<input\s+class="review-star-input"\s+'
                r'id="reviewRating4"\s+type="radio"\s+name="rating"\s+'
                r'value="4"\s+aria-label="4つ星"\s+required\s+checked\s*>'
            ),
        )

    @patch("apps.recipes.views.analyze_allergens", return_value=[[]])
    def test_recipe_review_is_persisted_updated_and_sorted(self, analyze):
        self.login_as(self.user_email)
        url = f"/recipes/{self.recipe_id}/reviews"
        self.assertEqual(
            self.client.post(
                url,
                data={"rating": "4", "comment": "最初のレビュー"},
            ).status_code,
            302,
        )
        self.login_as(self.other_user_email)
        self.client.post(url, data={"rating": "2", "comment": "低評価のレビュー"})

        self.login_as(self.user_email)
        self.client.post(url, data={"rating": "5", "comment": "更新後のレビュー"})
        detail = self.client.get(f"/recipes/{self.recipe_id}?sort=rating-asc")
        text = detail.get_data(as_text=True)
        self.assertEqual(detail.status_code, 200)
        self.assertIn("平均評価：★ 3.5（2件）", text)
        self.assertIn("更新後のレビュー", text)
        self.assertNotIn("最初のレビュー", text)
        self.assertLess(
            text.index("低評価のレビュー"),
            text.index("更新後のレビュー"),
        )
        with self.app.app_context():
            account = Account.query.filter_by(email=self.user_email).one()
            own_reviews = ContentReview.query.filter_by(
                account_id=account.id,
                recipe_id=self.recipe_id,
            ).all()
            self.assertEqual(len(own_reviews), 1)
            self.assertEqual(own_reviews[0].rating, 5)

    @patch("apps.recipes.views.analyze_allergens", return_value=[[]])
    def test_review_validation_and_user_account_requirement(self, analyze):
        url = f"/recipes/{self.recipe_id}/reviews"
        self.client.post(url, data={"rating": "5", "comment": "未ログイン"})
        self.login_as(self.restaurant_email)
        self.client.post(url, data={"rating": "5", "comment": "店舗アカウント"})
        self.login_as(self.user_email)
        for data in (
            {"rating": "0", "comment": "評価なし"},
            {"rating": "6", "comment": "範囲外"},
            {"rating": "3", "comment": "   "},
            {"rating": "3", "comment": "長文" * 501},
        ):
            self.client.post(url, data=data)

        with self.app.app_context():
            self.assertEqual(ContentReview.query.count(), 0)
        response = self.client.get(f"/recipes/{self.recipe_id}")
        self.assertIn(
            "レビューは1〜1000文字で入力してください。",
            response.get_data(as_text=True),
        )

    @patch("apps.restaurants.views.place_details", return_value=PLACE)
    def test_store_reviews_are_scoped_to_place_id(self, details):
        self.login_as(self.user_email)
        response = self.client.post(
            "/restaurants/detail/place123/reviews",
            data={"rating": "5", "comment": "店舗のレビュー"},
        )
        self.assertEqual(response.status_code, 302)
        detail = self.client.get("/restaurants/detail/place123")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("店舗のレビュー", detail.get_data(as_text=True))
        details.assert_called_once_with("place123")

        other_detail = self.client.get("/restaurants/detail/place456")
        self.assertNotIn("店舗のレビュー", other_detail.get_data(as_text=True))
        with self.app.app_context():
            review = ContentReview.query.one()
            self.assertIsNone(review.recipe_id)
            self.assertEqual(review.place_id, "place123")

    def test_sample_store_reviews_persist(self):
        self.login_as(self.user_email)
        self.client.post(
            "/restaurants/detail/reviews",
            data={"rating": "3", "comment": "サンプル店舗レビュー"},
        )
        response = self.client.get("/restaurants/detail")
        self.assertIn("サンプル店舗レビュー", response.get_data(as_text=True))
        with self.app.app_context():
            review = ContentReview.query.one()
            self.assertEqual(review.place_id, "sample-restaurant")


if __name__ == "__main__":
    unittest.main()
