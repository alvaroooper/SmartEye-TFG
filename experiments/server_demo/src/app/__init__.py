# src/app/__init__.py
from flask import Flask # type: ignore
from pathlib import Path
from src.core.config import Config # type: ignore
from src.app.api.routes import api_bp # type: ignore


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # Carpeta donde se guardarán las imágenes subidas
    upload_dir = Path(__file__).parent / "uploads"
    app.config["UPLOAD_FOLDER"] = upload_dir
    
    # Registrar blueprints
    app.register_blueprint(api_bp, url_prefix="/api")

    return app