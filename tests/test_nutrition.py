import io
import json
import unittest
from unittest.mock import patch

from apps import create_app
from apps.auth.models import Account
from apps.extensions import db


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
