
from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import generate_password_hash, check_password_hash

auth = Blueprint(
    "auth",
    __name__,
    template_folder="templates",
)

# DB導入までの仮データ保存領域
users_data = {}
restaurants_data = {}


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # 一般ユーザーを検索
        user = users_data.get(email)
        account_type = "user"

        # 一般ユーザーに存在しなければ店舗アカウントを検索
        if user is None:
            user = restaurants_data.get(email)
            account_type = "restaurant"

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["email"] = email
            session["account_type"] = account_type

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

        if email in users_data or email in restaurants_data:
            return render_template(
                "auth/signin.html",
                error="このメールアドレスは既に登録されています。"
            )

        users_data[email] = {
            "name": name,
            "password": generate_password_hash(password),
        }

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

        if email in users_data or email in restaurants_data:
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
