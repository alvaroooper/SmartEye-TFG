from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory # type: ignore
from pathlib import Path
import numpy as np # type: ignore
import cv2 # type: ignore

from src.app.services.detection_factory import get_detection_task, list_models_and_modes # type: ignore

ui_bp = Blueprint("ui_pages", __name__)

OUTPUT_DIR = Path("outputs").resolve()
OUTPUT_DIR.mkdir(exist_ok=True)


@ui_bp.get("/")
def home():
    models_config = list_models_and_modes()
    return render_template(
        "index.html",
        result_image=None,
        result_json=None,
        models_config=models_config,
        modelo="yolo",
        modo="",
    )

@ui_bp.get("/outputs/<string:filename>")
def get_output_image(filename: str):
    """
    Sirve las imágenes que guardan las tasks en la carpeta outputs/.
    """
    # convertir Path a str
    return send_from_directory(str(OUTPUT_DIR), filename)
    

@ui_bp.post("/analyze")
def analyze():
    if "image" not in request.files:
        return redirect(url_for("ui_pages.home"))

    file = request.files["image"]
    if file.filename == "":
        return redirect(url_for("ui_pages.home"))

    modelo = request.form.get("modelo", "yolo")
    modo = request.form.get("modo")  # default None

    # Leer imagen en numpy (igual que en /api/detect)
    image_bytes = file.read()
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Obtener la tarea adecuada (yolo / mediapipe + modo)
    try:
        task = get_detection_task(modelo, modo)
    except ValueError as e:
        return render_template("index.html", error=str(e))

    # Ejecutar el modelo REAL (ya dibuja y guarda en outputs/)
    result = task.run(image)

    # ---------------- CLAVE PARA MOSTRAR LA IMAGEN ----------------
    # result["output_image"] es algo como: "outputs\\mediapipe_pose_xxx.png"
    output_path_str = result.get("output_image", "")
    output_name = Path(output_path_str).name  # nos quedamos solo con "mediapipe_pose_xxx.png"

    # Construimos la URL a /outputs/<filename>
    img_url = url_for("ui_pages.get_output_image", filename=output_name)
    # --------------------------------------------------------------

    models_config = list_models_and_modes()

    return render_template(
        "index.html",
        result_image=img_url,
        result_json=result,
        modelo=modelo,
        modo=modo or "",
        models_config=models_config,
    )