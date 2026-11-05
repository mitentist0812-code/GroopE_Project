from flask import Blueprint, redirect, render_template, url_for

auth = Blueprint(
    "auth",
    __name__,
    template_folder="templates",
)


@auth.get("/login")
def login():
    return render_template("auth/login.html")


@auth.get("/signup")
def signup():
    return render_template("auth/signin.html")


@auth.get("/signup/restaurant")
def signup_restaurant():
    return render_template("auth/signin_restaurant.html")


@auth.get("/logout")
def logout():
    return redirect(url_for("auth.login"))
