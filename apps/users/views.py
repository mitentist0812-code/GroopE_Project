from flask import Blueprint, render_template

users = Blueprint("users", __name__, template_folder="templates")


@users.get("/")
def mypage():
    return render_template("users/mypage.html")


@users.get("/favorites")
def favorite():
    return render_template("users/favorite.html")


@users.get("/history")
def history():
    return render_template("users/history.html")


@users.get("/settings")
def setting():
    return render_template("users/setting.html")
