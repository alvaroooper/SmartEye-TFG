import cv2  # type: ignore
import numpy as np  # type: ignore
import torch  # type: ignore
import uuid
from pathlib import Path

from src.app.services.models.base import DetectionTask  # type: ignore


class YoloDefaultTask(DetectionTask):
    """Detección general de objetos con YOLO, guardando la imagen y devolviendo JSON."""

    def __init__(self) -> None:
        # Carga perezosa: el modelo se carga la primera vez que se use
        self._model = None

    def _ensure_model_loaded(self) -> None:
        if self._model is None:
            # Puedes ajustar el modelo (yolov5s, yolov5m...) si quieres
            self._model = torch.hub.load(
                "ultralytics/yolov5", "yolov5s", pretrained=True
            )
            # Opcional: ajustar umbral de confianza
            # self._model.conf = 0.25

    def run(self, image: np.ndarray):
        # 1) Asegurar que el modelo está cargado
        self._ensure_model_loaded()

        # 2) Ejecutar YOLO sobre la imagen
        results = self._model(image)

        # 3) Pasar resultados a DataFrame de pandas y luego a detecciones limpias
        df = results.pandas().xyxy[0]  # xmin, ymin, xmax, ymax, confidence, class, name

        detections = []

        for _, row in df.iterrows():
            xmin = float(row["xmin"])
            ymin = float(row["ymin"])
            xmax = float(row["xmax"])
            ymax = float(row["ymax"])
            conf = float(row["confidence"])
            label = str(row["name"])

            # Guardar la info en el JSON
            detections.append(
                {
                    "label": label,
                    "confidence": conf,
                    "bbox": {
                        "xmin": xmin,
                        "ymin": ymin,
                        "xmax": xmax,
                        "ymax": ymax,
                    },
                }
            )

            # 4) Dibujar la caja y el texto sobre la imagen BGR
            p1 = (int(xmin), int(ymin))
            p2 = (int(xmax), int(ymax))

            cv2.rectangle(image, p1, p2, (0, 255, 0), 2)

            text = f"{label} {conf:.2f}"
            # Posición del texto (un poco por encima de la caja)
            text_org = (int(xmin), int(max(ymin - 10, 0)))
            cv2.putText(
                image,
                text,
                text_org,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

        # 5) Guardar la imagen procesada en outputs/
        OUTPUT_DIR = Path("outputs")
        OUTPUT_DIR.mkdir(exist_ok=True)
        out_name = OUTPUT_DIR / f"yolo_default_{uuid.uuid4().hex}.png"
        cv2.imwrite(str(out_name), image)

        # 6) Devolver JSON con detecciones + ruta de imagen
        return {
            "model": "yolo",
            "mode": "default",
            "detections": detections,
            "output_image": str(out_name),
        }
