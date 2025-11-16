import cv2 # type: ignore
import mediapipe as mp # type: ignore
import numpy as np # type: ignore
import uuid, os
from pathlib import Path

from src.app.services.models.base import DetectionTask # type: ignore

mp_hands = mp.solutions.hands

class MediapipeHandsTask(DetectionTask):
    """Adaptación de tu deteccionManos.py para UNA imagen."""

    def __init__(self) -> None:
        self._hands = mp_hands.Hands(
            static_image_mode=True,
            model_complexity=0,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def run(self, image: np.ndarray):
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self._hands.process(image_rgb)

        hands = []
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                coords = [
                    {"x": lm.x, "y": lm.y, "z": lm.z}
                    for lm in hand_landmarks.landmark
                ]
                hands.append(coords)
                # Dibujar sobre la imagen BGR original
                mp.solutions.drawing_utils.draw_landmarks(
                    image, hand_landmarks, mp_hands.HAND_CONNECTIONS
                )

        # Guardar imagen procesada
        

        OUTPUT_DIR = Path("outputs")
        OUTPUT_DIR.mkdir(exist_ok=True)
        out_name = OUTPUT_DIR / f"mediapipe_hands_{uuid.uuid4().hex}.png"
        cv2.imwrite(str(out_name), image)

        return {
            "model": "mediapipe",
            "mode": "hands",
            "num_hands": len(hands),
            # "hands": hands,
            "output_image": str(out_name),
        }
