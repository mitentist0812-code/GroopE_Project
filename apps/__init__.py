from flask import Flask


def create_app():
    app = Flask(__name__)
    app.config.from_mapping(SECRET_KEY="your-secret-key")

    from apps.auth import auth
    from apps.home import home
    from apps.nutrition import nutrition
    from apps.recipes import recipes
    from apps.restaurants import restaurants
    from apps.users import users

    app.register_blueprint(auth, url_prefix="/auth")
    app.register_blueprint(home)
    app.register_blueprint(nutrition, url_prefix="/nutrition")
    app.register_blueprint(recipes, url_prefix="/recipes")
    app.register_blueprint(restaurants, url_prefix="/restaurants")
    app.register_blueprint(users, url_prefix="/users")
    return app
