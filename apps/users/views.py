from flask import Blueprint, render_template, session
from sqlalchemy.orm import selectinload

from apps.auth.models import Account
from apps.recipes.models import Recipe_list, RecipePhoto

users = Blueprint("users", __name__, template_folder="templates")


@users.get("/")
def mypage():
    email = session.get("email")
    account = Account.query.filter_by(email=email).first() if email else None
    recipes = []
    if account:
        recipes = (Recipe_list.query.options(
                       selectinload(Recipe_list.photos).load_only(
                           RecipePhoto.id, RecipePhoto.recipe_id, RecipePhoto.step_index,
                       ))
                   .filter_by(account_id=account.id)
                   .order_by(Recipe_list.created_at.desc(), Recipe_list.id.desc()).all())
    return render_template("users/mypage.html", posted_recipes=recipes)


@users.get("/favorites")
def favorite():
    return render_template("users/favorite.html")


@users.get("/history")
def history():
    return render_template("users/history.html")


@users.get("/settings")
def setting():
    return render_template("users/setting.html")
