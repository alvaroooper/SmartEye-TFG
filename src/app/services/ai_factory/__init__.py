from .yolo.launcher import YoloLauncher
from .mediapipe_modelo.launcher import MediaPipeLauncher

class AIFactory:
    @staticmethod
    def get_launcher(nombre_modelo: str):
        modelo = nombre_modelo.lower()
        if modelo == "yolo":
            return YoloLauncher()
        elif modelo == "mediapipe":
            return MediaPipeLauncher()
        else:
            raise ValueError(f"Modelo IA '{nombre_modelo}' no registrado en el Factory.")