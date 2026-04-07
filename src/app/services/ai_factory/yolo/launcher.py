from app.services.ai_factory.interface import IALauncherBase
from .deteccion import procesar_deteccion

class YoloLauncher(IALauncherBase):
    def __init__(self):
        # Aquí mapeamos el string que vendrá de la BD a la función real
        self.modos_soportados = {
            "deteccion": procesar_deteccion
        }

    def ejecutar_modo(self, modo_nombre: str, imagen_path: str):
        modo_func = self.modos_soportados.get(modo_nombre.lower())
        if not modo_func:
            raise ValueError(f"El modo '{modo_nombre}' no está implementado en YOLO.")
        
        return modo_func(imagen_path)