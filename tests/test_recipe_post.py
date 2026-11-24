import base64
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask_migrate import upgrade

from apps import create_app
from apps.auth.models import Account
from apps.extensions import db
from apps.recipes.models import Recipe_list, RecipePhoto


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a0u0AAAAASUVORK5CYII="
)


class RecipePostTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "recipes.sqlite"
        self.config = {
            "TESTING": True,
            "SECRET_KEY": "test-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + self.database_path.as_posix(),
        }
        self.app = create_app(self.config)
        with self.app.app_context():
            db.create_all()
            db.session.add_all([
                Account(email="one@example.com", name="One", account_type="user", password_hash="hash"),
                Account(email="two@example.com", name="Two", account_type="user", password_hash="hash"),
            ])
            db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def login(self, email="one@example.com"):
        with self.client.session_transaction() as session:
            session["email"] = email

    @patch("apps.recipes.views.analyze_allergens", return_value=[[]])
    def test_post_persists_photos_and_appears_in_search_and_own_page(self, analyze):
        self.login()
        response = self.client.post("/recipes/post", data={
            "title": "野菜カレー",
            "ingredient_name[]": ["玉ねぎ", "にんじん"],
            "ingredient_amount[]": ["1個", "2本"],
            "process[]": ["切る", "煮る"],
            "dishimg": (io.BytesIO(PNG), "dish.png"),
            "process_img[]": [(io.BytesIO(b""), ""), (io.BytesIO(PNG), "step.png")],
        }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/users/")

        with self.app.app_context():
            recipe = Recipe_list.query.one()
            self.assertEqual(recipe.ingredients, "玉ねぎ 1個\nにんじん 2本")
            self.assertEqual(recipe.steps, ["切る", "煮る"])
            self.assertEqual({photo.step_index for photo in recipe.photos}, {None, 1})
            recipe_id = recipe.id
            main_id = recipe.main_photo.id
            step_id = next(photo.id for photo in recipe.photos if photo.step_index == 1)
        photo = self.client.get(f"/recipes/photos/{main_id}")
        self.assertEqual(photo.data, PNG)
        self.assertEqual(photo.content_type, "image/png")
        self.assertEqual(photo.headers["X-Content-Type-Options"], "nosniff")
        main_url = f'/recipes/photos/{main_id}'
        step_url = f'/recipes/photos/{step_id}'
        recipe_url = f'/recipes/{recipe_id}'
        search = self.client.get("/recipe-results?keyword=にんじん").get_data(as_text=True)
        self.assertIn("野菜カレー", search)
        self.assertIn(main_url, search)
        self.assertIn(recipe_url, search)
        home = self.client.get("/").get_data(as_text=True)
        self.assertIn(main_url, home)
        self.assertIn(recipe_url, home)
        detail = self.client.get(recipe_url).get_data(as_text=True)
        self.assertIn(main_url, detail)
        self.assertIn(step_url, detail)
        self.assertIn("煮る", detail)
        page = self.client.get("/users/").get_data(as_text=True)
        self.assertIn("野菜カレー", page)
        self.assertIn(main_url, page)
        self.assertIn(step_url, page)
        self.assertIn("工程2の写真", page)

        restarted_app = create_app(self.config)
        restarted_client = restarted_app.test_client()
        with restarted_client.session_transaction() as session:
            session["email"] = "one@example.com"
        self.assertIn("野菜カレー", restarted_client.get("/users/").get_data(as_text=True))
        with restarted_app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.login("two@example.com")
        self.assertNotIn("野菜カレー", self.client.get("/users/").get_data(as_text=True))

    def test_requires_existing_account_and_valid_input(self):
        payload = {"title": "A", "ingredient_name[]": ["onion"], "ingredient_amount[]": ["1"]}
        self.assertEqual(self.client.post("/recipes/post", data=payload).status_code, 401)
        self.login("missing@example.com")
        self.assertEqual(self.client.post("/recipes/post", data=payload).status_code, 403)
        self.login()
        self.assertEqual(self.client.post("/recipes/post", data={**payload, "ingredient_amount[]": [""]}).status_code, 400)
        self.assertEqual(self.client.post("/recipes/post", data={
            **payload, "dishimg": (io.BytesIO(b"x" * (300 * 1024 + 1)), "large.png"),
        }).status_code, 400)
        self.assertEqual(self.client.post("/recipes/post", data={
            **payload, "dishimg": (io.BytesIO(b"<svg></svg>"), "image.svg"),
        }).status_code, 400)
        with self.app.app_context():
            self.assertEqual(Recipe_list.query.count(), 0)
            self.assertEqual(RecipePhoto.query.count(), 0)

    @patch("apps.recipes.views.analyze_allergens", return_value=[[]])
    def test_existing_recipe_without_photo_has_detail_and_placeholder(self, analyze):
        with self.app.app_context():
            recipe = Recipe_list(recipe_name="画像なし", ingredients="水", description="煮る")
            db.session.add(recipe)
            db.session.commit()
            recipe_id = recipe.id
        detail = self.client.get(f"/recipes/{recipe_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("写真なし", detail.get_data(as_text=True))
        self.assertIn("煮る", detail.get_data(as_text=True))
        self.assertEqual(self.client.get("/recipes/99999").status_code, 404)


class RecipeMigrationTests(unittest.TestCase):
    def test_upgrade_preserves_existing_recipes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "migration.sqlite"
            app = create_app({
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///" + path.as_posix(),
            })
            with app.app_context():
                upgrade(revision="71fd59c0a3e4")
                with db.engine.begin() as connection:
                    connection.exec_driver_sql(
                        "INSERT INTO recipe_list (recipe_name, ingredients, description) VALUES (?, ?, ?)",
                        ("existing", "onion", "cook"),
                    )
                upgrade()
                recipe = Recipe_list.query.one()
                self.assertEqual(recipe.recipe_name, "existing")
                self.assertIsNone(recipe.account_id)
                self.assertIsNone(recipe.steps)
                db.session.remove()
                db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
