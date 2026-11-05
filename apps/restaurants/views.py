from flask import Blueprint, render_template

restaurants = Blueprint("restaurants", __name__, template_folder="templates")


@restaurants.get("/")
def restaurant():
    return render_template("restaurants/restaurant.html")


@restaurants.get("/detail")
def restaurant_detail():
    return render_template("restaurants/restaurant_detail.html")


@restaurants.get("/menu")
def menu_management():
    return render_template("restaurants/menu_management.html")


@restaurants.get("/reservations")
def reservation_management():
    return render_template("restaurants/reservation_management.html")


@restaurants.get("/reservations/new")
def reservation_form():
    return render_template("restaurants/reservation_form.html")
