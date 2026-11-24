from flask import Blueprint, current_app, flash, make_response, redirect, render_template, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from apps.allergens import AllergenModelUnavailable, analyze_allergens
from apps.auth.models import Account
from apps.extensions import db
from apps.review_utils import current_reviewer, load_reviews, save_review_form

from .models import RecipeFavorite, Recipe_list, RecipePhoto

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
        if account.account_type != "user":
            return render_template("recipes/post_recipe.html", error="店舗アカウントではレシピを投稿できません。"), 403

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


@recipes.get("/<int:recipe_id>")
def recipe_detail(recipe_id):
    recipe = db.first_or_404(
        db.select(Recipe_list).options(
            selectinload(Recipe_list.photos).load_only(
                RecipePhoto.id, RecipePhoto.recipe_id, RecipePhoto.step_index,
            )
        ).where(Recipe_list.id == recipe_id)
    )
    reviewer = current_reviewer()
    is_favorite = bool(
        reviewer
        and RecipeFavorite.query.filter_by(
            account_id=reviewer.id,
            recipe_id=recipe.id,
        ).first()
    )
    reviews, average_rating, own_review = load_reviews(
        recipe_id=recipe.id,
        reviewer=reviewer,
        sort=request.args.get("sort", "newest"),
    )
    recipe_text = "\n".join(
        text for text in (
            recipe.recipe_name,
            recipe.ingredients,
            recipe.description,
        )
        if text
    )
    allergen_model_error = False
    try:
        possible_allergens = analyze_allergens([recipe_text])[0]
    except AllergenModelUnavailable:
        current_app.logger.exception("レシピのアレルゲン候補判定に失敗しました")
        possible_allergens = []
        allergen_model_error = True

    return render_template(
        "recipes/recipe_detail.html",
        recipe=recipe,
        is_favorite=is_favorite,
        reviews=reviews,
        average_rating=average_rating,
        own_review=own_review,
        reviewer=reviewer,
        review_sort=request.args.get("sort", "newest"),
        possible_allergens=possible_allergens,
        allergen_model_error=allergen_model_error,
    )


@recipes.post("/<int:recipe_id>/reviews")
def submit_recipe_review(recipe_id):
    recipe = db.get_or_404(Recipe_list, recipe_id)
    email = session.get("email")
    account = Account.query.filter_by(email=email).first() if email else None
    error = save_review_form(
        account,
        request.form,
        recipe_id=recipe.id,
    )
    if error:
        flash(error, "error")
    else:
        flash("レビューを投稿しました。", "success")
    return redirect(url_for("recipes.recipe_detail", recipe_id=recipe.id))
