# src/app/api/routes.py
from flask import Blueprint, jsonify, request, current_app, send_from_directory # type: ignore
from pathlib import Path

from src.app.services.image_service import ( # type: ignore
    save_uploaded_image,
    list_images,
    delete_image,
    get_image_path,
)
from src.app.services.status_service import get_status # type: ignore

api_bp = Blueprint("api", __name__)


@api_bp.get("/health")
def health_check():
    """
    Endpoint simple para comprobar que el servidor funciona.
    """
    return jsonify({
        "status": "ok",
        "message": "server_demo funcionando correctamente",
    })


# ------------------------------
#  SUBIR IMAGEN
# ------------------------------
@api_bp.post("/upload_image")
def upload_image():
    """
    Recibe una imagen por formulario multipart y la guarda en /uploads.
    """
    if "image" not in request.files:
        return jsonify({"error": "Falta el campo 'image'"}), 400

    file = request.files["image"]
    upload_dir: Path = current_app.config["UPLOAD_FOLDER"]

    try:
        new_name, save_path = save_uploaded_image(upload_dir, file)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "filename": new_name,
        "saved_in": str(save_path),
    }), 201


# ------------------------------
#  LISTAR IMÁGENES
# ------------------------------
@api_bp.get("/images")
def list_uploaded_images():
    """
    Devuelve la lista de imágenes subidas.
    """
    upload_dir: Path = current_app.config["UPLOAD_FOLDER"]
    images = list_images(upload_dir)
    return jsonify(images), 200


# ------------------------------
#  BORRAR IMAGEN 
# ------------------------------
@api_bp.delete("/images/<filename>")
def delete_uploaded_image(filename: str):
    """
    Elimina una imagen subida por su nombre de fichero.
    """
    upload_dir: Path = current_app.config["UPLOAD_FOLDER"]

    deleted = delete_image(upload_dir, filename)
    if not deleted:
        return jsonify({"error": "Imagen no encontrada"}), 404

    return jsonify({"message": f"Imagen '{filename}' eliminada"}), 200


# ------------------------------
#  DESCARGAR IMAGEN
# ------------------------------
@api_bp.get("/images/<filename>/download")
def download_image(filename: str):
    """
    Devuelve el archivo de imagen para descargar/visualizar.
    """
    upload_dir: Path = current_app.config["UPLOAD_FOLDER"]

    path = get_image_path(upload_dir, filename)
    if path is None:
        return jsonify({"error": "Imagen no encontrada"}), 404

    # send_from_directory necesita la carpeta y el nombre
    return send_from_directory(upload_dir, path.name, as_attachment=False)


# ------------------------------
#  ESTADO DEL SERVIDOR 
# ------------------------------
@api_bp.get("/status")
def status():
    """
    Devuelve información de estado del servidor: nº de imágenes, versión de Python, etc.
    """
    upload_dir: Path = current_app.config["UPLOAD_FOLDER"]
    debug = current_app.debug
    data = get_status(upload_dir, debug)
    return jsonify(data), 200
