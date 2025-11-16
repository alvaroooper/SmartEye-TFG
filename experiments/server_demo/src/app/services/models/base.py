# src/app/services/models/base.py
from abc import ABC, abstractmethod
from typing import Any
import numpy as np # type: ignore

class DetectionTask(ABC):
    """Interfaz común para cualquier tarea de detección/procesado de imagen."""

    @abstractmethod
    def run(self, image: "np.ndarray") -> Any:
        """Procesa una imagen BGR y devuelve algo serializable a JSON."""
        raise NotImplementedError
