from typing import Dict

from src.app.services.models.base import DetectionTask # type: ignore
from src.app.services.models.yolo.default_task import YoloDefaultTask # type: ignore

class YoloService:
    """Mini-factory de YOLO, listo para futuros modos (people, vehicles...)."""

    def __init__(self) -> None:
        self._tasks: Dict[str, DetectionTask] = {
            "default": YoloDefaultTask(),
            # "people": YoloPeopleTask(), ...
        }

    def get_task(self, mode: str | None) -> DetectionTask:
        key = (mode or "default").lower()
        if key not in self._tasks:
            raise ValueError(f"Modo de YOLO '{key}' no soportado")
        return self._tasks[key]
