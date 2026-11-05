from flask import Blueprint, render_template

nutrition = Blueprint("nutrition", __name__, template_folder="templates")


@nutrition.get("/calorie")
def calorie():
    return render_template("nutrition/calorie.html")
