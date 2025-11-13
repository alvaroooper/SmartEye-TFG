from flask import Blueprint, jsonify # type: ignore

api_bp = Blueprint("api", __name__)

@api_bp.get("/health")
def health_check():
    """
    Endpoint simple para comprobar que el servidor funciona.
    """
    return jsonify(
        {
            "status": "ok",
            "message": "server_demo funcionando correctamente",
        }
    )
