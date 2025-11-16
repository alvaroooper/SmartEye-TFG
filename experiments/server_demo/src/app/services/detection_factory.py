from src.app.services.models.base import DetectionTask # type: ignore
from src.app.services.models.mediapipe.service import MediapipeService # type: ignore
from src.app.services.models.yolo.service import YoloService # type: ignore
_mediapipe_service = MediapipeService()
_yolo_service = YoloService()


def get_detection_task(model: str, mode: str | None = None) -> DetectionTask:
    """
    Factory global:
    - model: 'mediapipe' | 'yolo' | 'mock' | ...
    - mode: depende del modelo ('hands', 'pose', 'default', etc.)
    """
    m = model.lower()

    if m == "mediapipe":
        return _mediapipe_service.get_task(mode)

    if m == "yolo":
        return _yolo_service.get_task(mode)

    raise ValueError(f"Modelo '{model}' no soportado")
