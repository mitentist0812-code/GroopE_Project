from flask import Blueprint, render_template

home = Blueprint("home", __name__, template_folder="templates")


@home.get("/")
def top():
    return render_template("home/top.html")


@home.get("/results")
def results():
    return render_template("home/results.html")
