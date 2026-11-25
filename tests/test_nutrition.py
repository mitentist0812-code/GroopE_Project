import io
import json
import unittest
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from apps import create_app
from apps.auth.models import Account
from apps.extensions import db
from apps.nutrition.models import CalorieHistory


class NutritionTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            db.session.add(Account(
                email="test@example.com", name="test", account_type="user", password_hash="unused",
            ))
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def login(self):
        with self.client.session_transaction() as session:
            session["email"] = "test@example.com"
        self.client.get("/nutrition/calorie")
        with self.client.session_transaction() as session:
            return session["calorie_csrf"]

    def test_ingredient_list_is_collapsed_with_edit_inside(self):
        response = self.client.get("/nutrition/calorie")
        html = response.get_data(as_text=True)
        details = html.split('<details id="ingredient-details">', 1)[1].split("</details>", 1)[0]
        self.assertIn("材料一覧を見る", details)
        self.assertIn('id="ingredient-list"', details)
        self.assertIn('id="edit-ingredients"', details)
        self.assertLess(html.index('id="calorie-total"'), html.index('<details id="ingredient-details">'))

    def test_food_search_uses_official_data(self):
        self.login()
        response = self.client.get("/nutrition/foods", query_string={"q": "うるち米"})
        self.assertEqual(response.status_code, 200)
        rice = next(food for food in response.json["foods"] if food["id"] == "01088")
        self.assertEqual(rice["kcal_per_100g"], 156)

    @patch("apps.nutrition.views._analyze_image")
    def test_analysis_requires_authentication_and_csrf(self, analyze):
        response = self.client.post("/nutrition/calorie/analyze")
        self.assertEqual(response.status_code, 401)
        self.login()
        response = self.client.post("/nutrition/calorie/analyze")
        self.assertEqual(response.status_code, 403)
        analyze.assert_not_called()

    @patch("apps.nutrition.views._analyze_image")
    def test_analysis_validates_photo_and_returns_result(self, analyze):
        token = self.login()
        analyze.return_value = {"is_food": True, "dish": "ご飯", "ingredients": [{"name": "ご飯", "grams": 150}]}
        response = self.client.post("/nutrition/calorie/analyze", data={
            "csrf_token": token, "photo": (io.BytesIO(b"not an image"), "meal.jpg"),
        })
        self.assertEqual(response.status_code, 400)
        analyze.assert_not_called()
        response = self.client.post("/nutrition/calorie/analyze", data={
            "csrf_token": token, "photo": (io.BytesIO(b"\xff\xd8\xfftest"), "meal.jpg"),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["ingredients"][0]["grams"], 150)
        self.assertEqual(response.json["ingredients"][0]["food"]["id"], "01088")
        self.assertEqual(response.json["ingredients"][0]["food"]["kcal_per_100g"], 156)
        self.assertTrue(response.json["history_key"])
        analyze.assert_called_once_with(b"\xff\xd8\xfftest")

    @patch("apps.nutrition.views._analyze_image")
    def test_analysis_marks_unknown_food_without_guessing(self, analyze):
        token = self.login()
        analyze.return_value = {"is_food": True, "dish": "料理", "ingredients": [
            {"name": "玉ねぎ", "grams": 80}, {"name": "存在しない材料", "grams": 10},
        ]}
        response = self.client.post("/nutrition/calorie/analyze", data={
            "csrf_token": token, "photo": (io.BytesIO(b"\xff\xd8\xfftest"), "meal.jpg"),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["ingredients"][0]["food"]["id"], "06153")
        self.assertIsNone(response.json["ingredients"][1]["food"])

    @patch("apps.nutrition.views._analyze_image")
    def test_analysis_rejects_oversized_photo(self, analyze):
        token = self.login()
        response = self.client.post("/nutrition/calorie/analyze", data={
            "csrf_token": token,
            "photo": (io.BytesIO(b"\xff\xd8\xff" + b"x" * (5 * 1024 * 1024)), "meal.jpg"),
        })
        self.assertIn(response.status_code, (400, 413))
        self.assertIn("5MB", response.json["error"])
        analyze.assert_not_called()

    def test_history_saves_updates_and_is_scoped_to_account(self):
        token = self.login()
        headers = {"X-CSRF-Token": token}
        payload = {"dish": "ご飯", "save_key": "test-key", "ingredients": [
            {"name": "ご飯", "grams": 150, "food_id": "01088"},
            {"name": "不明", "grams": 10, "food_id": None},
        ]}
        response = self.client.post("/nutrition/calorie/history", json=payload, headers=headers)
        self.assertEqual(response.status_code, 200)
        history_id = response.json["id"]
        retry = self.client.post("/nutrition/calorie/history", json=payload, headers=headers)
        self.assertEqual(retry.json["id"], history_id)
        page = self.client.get("/users/history")
        self.assertEqual(page.status_code, 200)
        self.assertIn("小計：約234 kcal（1件は未計算）", page.get_data(as_text=True))
        self.assertIn('id="calorie-history-tab"', page.get_data(as_text=True))
        self.assertEqual(page.headers["Cache-Control"], "no-store")

        payload["ingredients"] = [{"name": "ご飯", "grams": 200, "food_id": "01088"}]
        self.assertEqual(self.client.put(
            f"/nutrition/calorie/history/{history_id}", json=payload, headers=headers,
        ).status_code, 200)
        with self.app.app_context():
            entry = CalorieHistory.query.one()
            self.assertEqual(entry.total_calories, 312)
            self.assertEqual(entry.unmatched_count, 0)
            db.session.add(Account(email="other@example.com", name="other", account_type="user", password_hash="unused"))
            db.session.commit()
        self.assertIn("推定合計：約312 kcal", self.client.get("/users/history").get_data(as_text=True))

        with self.client.session_transaction() as session:
            session["email"] = "other@example.com"
        self.assertEqual(self.client.put(
            f"/nutrition/calorie/history/{history_id}", json=payload, headers=headers,
        ).status_code, 404)
        self.assertNotIn("推定合計：約312 kcal", self.client.get("/users/history").get_data(as_text=True))

    def test_history_rejects_invalid_input_and_reports_storage_failure(self):
        payload = {"dish": "料理", "save_key": "test-key", "ingredients": [{"name": "ご飯", "grams": 100, "food_id": "01088"}]}
        self.assertEqual(self.client.post("/nutrition/calorie/history", json=payload).status_code, 401)
        token = self.login()
        self.assertEqual(self.client.post("/nutrition/calorie/history", json=payload).status_code, 403)
        headers = {"X-CSRF-Token": token}
        for grams, food_id in [(0, "01088"), (float("nan"), "01088"), (10 ** 400, "01088"), (100, "not-a-food")]:
            with self.subTest(grams=grams, food_id=food_id):
                invalid = {"dish": "料理", "save_key": "test-key", "ingredients": [{"name": "ご飯", "grams": grams, "food_id": food_id}]}
                self.assertEqual(self.client.post("/nutrition/calorie/history", json=invalid, headers=headers).status_code, 400)
        with patch.object(db.session, "commit", side_effect=SQLAlchemyError("failure")):
            response = self.client.post("/nutrition/calorie/history", json=payload, headers=headers)
        self.assertEqual(response.status_code, 500)
        self.assertIn("履歴を保存できませんでした", response.json["error"])
        with self.app.app_context():
            self.assertEqual(CalorieHistory.query.count(), 0)

    @patch("apps.nutrition.views.urlopen")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_gemini_request_and_response_validation(self, urlopen):
        result = {"is_food": True, "dish": "ご飯", "ingredients": [{"name": "ご飯", "grams": 150}]}
        body = {"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"text": "thinking", "thought": True}, {"text": json.dumps(result)},
        ]}}]}
        urlopen.return_value.__enter__.return_value = io.BytesIO(json.dumps(body).encode())
        from apps.nutrition.views import _analyze_image
        self.assertEqual(_analyze_image(b"image"), result)
        req = urlopen.call_args.args[0]
        self.assertIn("gemini-3.5-flash-lite:generateContent", req.full_url)
        payload = json.loads(req.data)
        self.assertEqual(payload["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(payload["contents"][0]["parts"][1]["inline_data"]["mime_type"], "image/jpeg")

    @patch("apps.nutrition.views.urlopen")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_invalid_gemini_ingredient_is_rejected(self, urlopen):
        result = {"is_food": True, "dish": "ご飯", "ingredients": [{"name": "ご飯", "grams": -1}]}
        body = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(result)}]}}]}
        urlopen.return_value.__enter__.return_value = io.BytesIO(json.dumps(body).encode())
        from apps.nutrition.views import _analyze_image
        with self.assertRaises(ValueError):
            _analyze_image(b"image")


if __name__ == "__main__":
    unittest.main()
