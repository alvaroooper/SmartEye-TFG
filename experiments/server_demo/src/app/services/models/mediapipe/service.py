from typing import Dict

from src.app.services.models.base import DetectionTask # type: ignore
from src.app.services.models.mediapipe.hands_task import MediapipeHandsTask # type: ignore
from src.app.services.models.mediapipe.pose_task import MediapipePoseTask # type: ignore

class MediapipeService:
    """Mini-factory de MediaPipe: hands, pose, image..."""

    def __init__(self) -> None:
        self._tasks: Dict[str, DetectionTask] = {
            "hands": MediapipeHandsTask(),
            "pose": MediapipePoseTask(),
        }

    def get_task(self, mode: str | None) -> DetectionTask:
        key = (mode or "pose").lower()
        if key not in self._tasks:
            raise ValueError(f"Modo de MediaPipe '{key}' no soportado")
        return self._tasks[key]
