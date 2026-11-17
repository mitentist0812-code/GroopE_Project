
from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

from apps.extensions import db

from .models import Account

auth = Blueprint(
    "auth",
    __name__,
    template_folder="templates",
)


def _create_account(email, name, password, account_type, address=None, phone=None):
    account = Account(
        email=email,
        name=name,
        password_hash=generate_password_hash(password),
        account_type=account_type,
        address=address,
        phone=phone,
    )
    db.session.add(account)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if Account.query.filter_by(email=email).first():
            return False
        raise

    return True


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        account = Account.query.filter_by(email=email).first()

        if account and check_password_hash(account.password_hash, password):
            session.clear()
            session["email"] = email
            session["account_type"] = account.account_type
            session["name"] = account.name
            session["place_id"] = account.place_id

            return redirect(url_for("home.top"))

        return render_template(
            "auth/login.html",
            error="メールアドレスまたはパスワードが違います。"
        )

    return render_template("auth/login.html")


@auth.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("user-name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password-confirm", "")

        if not name or not email or not password:
            return render_template(
                "auth/signin.html",
                error="すべての必須項目を入力してください。"
            )

        if len(password) < 8:
            return render_template(
                "auth/signin.html",
                error="パスワードは8文字以上にしてください。"
            )

        if password != password_confirm:
            return render_template(
                "auth/signin.html",
                error="パスワードが一致しません。"
            )

        if Account.query.filter_by(email=email).first():
            return render_template(
                "auth/signin.html",
                error="このメールアドレスは既に登録されています。"
            )

        if not _create_account(email, name, password, "user"):
            return render_template(
                "auth/signin.html",
                error="このメールアドレスは既に登録されています。"
            )

        return redirect(url_for("auth.login"))

    return render_template("auth/signin.html")


@auth.route("/signup/restaurant", methods=["GET", "POST"])
def signup_restaurant():
    if request.method == "POST":
        name = request.form.get("restaurant_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")
        address = request.form.get("address", "").strip()
        phone = request.form.get("phone", "").strip()

        if not name or not email or not password or not address:
            return render_template(
                "auth/signin_restaurant.html",
                error="必須項目をすべて入力してください。"
            )

        if len(password) < 8:
            return render_template(
                "auth/signin_restaurant.html",
                error="パスワードは8文字以上にしてください。"
            )

        if password != password_confirm:
            return render_template(
                "auth/signin_restaurant.html",
                error="パスワードが一致しません。"
            )

        if Account.query.filter_by(email=email).first():
            return render_template(
                "auth/signin_restaurant.html",
                error="このメールアドレスは既に登録されています。"
            )

        if not _create_account(
            email, name, password, "restaurant", address=address, phone=phone
        ):
            return render_template(
                "auth/signin_restaurant.html",
                error="このメールアドレスは既に登録されています。"
            )

        return redirect(url_for("auth.login"))

    return render_template("auth/signin_restaurant.html")


@auth.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
