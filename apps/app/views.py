from flask import Blueprint

app = Blueprint(
    "app",
    __name__,
    template_folder="templates",
    static_folder="static",
)


@app.route("/")
def index():
    return "Hello, app!"
