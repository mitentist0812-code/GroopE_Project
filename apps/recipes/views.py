from flask import Blueprint, render_template

recipes = Blueprint("recipes", __name__, template_folder="templates")


@recipes.get("/post")
def post_recipe():
    return render_template("recipes/post_recipe.html")


@recipes.get("/detail")
def recipe_detail():
    return render_template("recipes/recipe_detail.html")
