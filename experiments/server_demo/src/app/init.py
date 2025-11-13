from flask import Flask # type: ignore
from src.core.config import Config # type: ignore
from src.app.api.routes import api_bp # type: ignore

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.register_blueprint(api_bp, url_prefix="/api")

    return app
