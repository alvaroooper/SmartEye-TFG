import cv2  # type: ignore
import mediapipe as mp  # type: ignore
import numpy as np  # type: ignore
import uuid
from pathlib import Path

from src.app.services.models.base import DetectionTask  # type: ignore

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils  # para dibujar landmarks


class MediapipePoseTask(DetectionTask):
    """Adaptación de tu deteccionPose.py con guardado de imagen y JSON."""

    def __init__(self) -> None:
        self._pose = mp_pose.Pose(
            static_image_mode=True,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.5,
        )

    def run(self, image: np.ndarray):
        # 1) BGR -> RGB para MediaPipe
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self._pose.process(image_rgb)

        landmarks = []

        if results.pose_landmarks:
            # 2) Guardar landmarks JSON
            for lm in results.pose_landmarks.landmark:
                landmarks.append({
                    "x": lm.x,
                    "y": lm.y,
                    "z": lm.z,
                    "visibility": lm.visibility,
                })

            # 3) Dibujar TODOS los landmarks de la pose sobre la imagen BGR original
            mp_drawing.draw_landmarks(
                image,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS
            )

        # 4) Guardar la imagen procesada en una carpeta 
        OUTPUT_DIR = Path("outputs")
        OUTPUT_DIR.mkdir(exist_ok=True)
        out_name = OUTPUT_DIR / f"mediapipe_pose_{uuid.uuid4().hex}.png"
        cv2.imwrite(str(out_name), image)

        # 5) Devolver JSON 
        return {
            "model": "mediapipe",
            "mode": "pose",
            "num_landmarks": len(landmarks),
            "landmarks": landmarks,
            "output_image": str(out_name),
        }
