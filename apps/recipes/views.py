from flask import Blueprint, current_app, flash, make_response, redirect, render_template, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from apps.auth.models import Account
from apps.extensions import db

from .models import Recipe_list, RecipePhoto

recipes = Blueprint("recipes", __name__, template_folder="templates")
MAX_PHOTO_BYTES = 300 * 1024
MAX_ROWS = 50


def _read_photo(upload, step_index=None):
    if not upload or not upload.filename:
        return None
    data = upload.stream.read(MAX_PHOTO_BYTES + 1)
    if len(data) > MAX_PHOTO_BYTES:
        raise ValueError("画像は1枚300KB以下にしてください。")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        content_type = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        content_type = "image/jpeg"
    elif data.startswith((b"GIF87a", b"GIF89a")):
        content_type = "image/gif"
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        content_type = "image/webp"
    else:
        raise ValueError("画像はPNG、JPEG、GIF、WebP形式で選択してください。")
    return RecipePhoto(data=data, content_type=content_type, step_index=step_index)


@recipes.route("/post", methods=["GET", "POST"])
def post_recipe():
    if request.method == "POST":
        email = session.get("email")
        if not email:
            return render_template("recipes/post_recipe.html", error="レシピを投稿するにはログインしてください。"), 401
        account = Account.query.filter_by(email=email).first()
        if not account:
            return render_template("recipes/post_recipe.html", error="アカウントを確認できません。再度ログインしてください。"), 403

        title = request.form.get("title", "").strip()
        names = request.form.getlist("ingredient_name[]")
        amounts = request.form.getlist("ingredient_amount[]")
        steps = [step.strip() for step in request.form.getlist("process[]")]
        step_images = request.files.getlist("process_img[]")
        if (not title or len(title) > 100 or not names or len(names) != len(amounts)
                or len(names) > MAX_ROWS or len(steps) > MAX_ROWS or len(step_images) > len(steps)
                or any(not name.strip() or not amount.strip() or len(name.strip()) > 200 or len(amount.strip()) > 200
                       for name, amount in zip(names, amounts))
                or any(len(step) > 10000 for step in steps)):
            return render_template(
                "recipes/post_recipe.html",
                error="レシピ名は100文字以内、材料名・分量は各200文字以内で入力してください。材料と工程は各50件以内、工程は各10000文字以内です。",
            ), 400

        try:
            photos = []
            main_photo = _read_photo(request.files.get("dishimg"))
            if main_photo:
                photos.append(main_photo)
            for index, image in enumerate(step_images):
                photo = _read_photo(image, index)
                if photo:
                    photos.append(photo)
        except ValueError as exc:
            return render_template("recipes/post_recipe.html", error=str(exc)), 400

        recipe = Recipe_list(
            recipe_name=title,
            ingredients="\n".join(f"{name.strip()} {amount.strip()}" for name, amount in zip(names, amounts)),
            description="\n\n".join(step for step in steps if step),
            steps=steps,
            account_id=account.id,
            photos=photos,
        )
        try:
            db.session.add(recipe)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("レシピの保存に失敗しました")
            return render_template("recipes/post_recipe.html", error="レシピを保存できませんでした。時間をおいて再度お試しください。"), 500
        flash("レシピを投稿しました。")
        return redirect(url_for("users.mypage"))

    return render_template("recipes/post_recipe.html")


@recipes.get("/photos/<int:photo_id>")
def recipe_photo(photo_id):
    photo = db.get_or_404(RecipePhoto, photo_id)
    response = make_response(photo.data)
    response.headers["Content-Type"] = photo.content_type
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@recipes.get("/detail")
def recipe_detail():
    return render_template("recipes/recipe_detail.html")


@recipes.get("/<int:recipe_id>")
def recipe_entry(recipe_id):
    recipe = db.first_or_404(
        db.select(Recipe_list).options(
            selectinload(Recipe_list.photos).load_only(
                RecipePhoto.id, RecipePhoto.recipe_id, RecipePhoto.step_index,
            )
        ).where(Recipe_list.id == recipe_id)
    )
    return render_template("recipes/recipe_entry.html", recipe=recipe)
