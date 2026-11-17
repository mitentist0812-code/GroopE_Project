
from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User

auth = Blueprint(
    "auth",
    __name__,
    template_folder="templates",
)

# 店舗アカウントはDB対応するまで仮データで管理
restaurants_data = {}


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # 一般ユーザーをDBから検索
        user = User.query.filter_by(email=email).first()
        account_type = "user"

        # 一般ユーザーに存在しなければ店舗アカウントを検索
        if user is None:
            user = restaurants_data.get(email)
            account_type = "restaurant"

        # パスワード照合
        if user:
            stored_password = (
                user.password if account_type == "user"
                else user["password"]
            )

            if check_password_hash(stored_password, password):
                session.clear()
                session["email"] = email
                session["account_type"] = account_type

                if account_type == "user":
                    session["user_id"] = user.user_id

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

        # DBと店舗データの両方でメールアドレスの重複を確認
        if User.query.filter_by(email=email).first() or email in restaurants_data:
            return render_template(
                "auth/signin.html",
                error="このメールアドレスは既に登録されています。"
            )

        # DBにユーザーを登録
        new_user = User(
            user_name=name,
            email=email,
            password=generate_password_hash(password),
        )

        db.session.add(new_user)
        db.session.commit()

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

        if User.query.filter_by(email=email).first() or email in restaurants_data:
            return render_template(
                "auth/signin_restaurant.html",
                error="このメールアドレスは既に登録されています。"
            )

        restaurants_data[email] = {
            "name": name,
            "password": generate_password_hash(password),
            "address": address,
            "phone": phone,
        }

        return redirect(url_for("auth.login"))

    return render_template("auth/signin_restaurant.html")


@auth.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
