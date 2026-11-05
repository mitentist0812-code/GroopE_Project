from flask import Flask


def create_app():
    app = Flask(__name__)

    app.config.from_mapping(
        SECRET_KEY="your-secret-key"
    )

    from apps.app import views as app_views
    app.register_blueprint(
        app_views.app,
        url_prefix="/app"
    )

    return app
