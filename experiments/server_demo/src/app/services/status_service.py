# src/app/services/status_service.py
from pathlib import Path
import platform
from .image_service import list_images # type: ignore


def get_status(upload_dir: Path, debug: bool) -> dict:
    """
    Construye un diccionario con información de estado del servidor.
    """
    images = list_images(upload_dir)
    total_size = sum(img["size_bytes"] for img in images)

    return {
        "status": "ok",
        "debug": debug,
        "python_version": platform.python_version(),
        "num_images": len(images),
        "total_images_size_bytes": total_size,
    }
