# src/app/services/image_service.py
from pathlib import Path
from typing import List, Dict, Tuple
from werkzeug.datastructures import FileStorage # type: ignore
from werkzeug.utils import secure_filename # type: ignore
import uuid

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def _is_allowed_extension(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def save_uploaded_image(upload_dir: Path, file: FileStorage) -> Tuple[str, Path]:
    """
    Valida y guarda una imagen subida en 'upload_dir'.
    Devuelve (nuevo_nombre, ruta_absoluta).
    Lanza ValueError con mensaje si hay problema.
    """
    if file.filename == "":
        raise ValueError("El archivo no tiene nombre")

    filename = secure_filename(file.filename)

    if not _is_allowed_extension(filename):
        raise ValueError("Extensión no permitida o archivo sin extensión")

    upload_dir.mkdir(exist_ok=True)

    ext = filename.rsplit(".", 1)[1].lower()
    new_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = upload_dir / new_name

    file.save(save_path)

    return new_name, save_path


def list_images(upload_dir: Path) -> List[Dict]:
    """
    Devuelve una lista de diccionarios con info de cada imagen en upload_dir.
    """
    upload_dir.mkdir(exist_ok=True)

    images = []
    for p in upload_dir.iterdir():
        if p.is_file() and _is_allowed_extension(p.name):
            images.append(
                {
                    "filename": p.name,
                    "size_bytes": p.stat().st_size,
                }
            )
    # Ordenar por nombre para resultados estables
    images.sort(key=lambda x: x["filename"])
    return images


def get_image_path(upload_dir: Path, filename: str) -> Path | None:
    """
    Devuelve la ruta absoluta de una imagen si existe y es válida, o None en caso contrario.
    """
    safe_name = secure_filename(filename)
    path = upload_dir / safe_name
    if path.exists() and path.is_file():
        return path
    return None


def delete_image(upload_dir: Path, filename: str) -> bool:
    """
    Intenta borrar la imagen 'filename' de upload_dir.
    Devuelve True si la ha borrado, False si no existía.
    """
    path = get_image_path(upload_dir, filename)
    if path is None:
        return False
    path.unlink()
    return True
