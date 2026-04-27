from app.services.ai_factory.interface import IALauncherBase
from .deteccion import procesar_deteccion
from .recortes import procesar_recortes_personas

class YoloLauncher(IALauncherBase):
    # Mapear el string procetente de la BD a la función real
    def __init__(self):
        self.modos_soportados = {
            "deteccion": procesar_deteccion,
            "recortes_personas": procesar_recortes_personas
        }

    # Recibir el nombre del modo, la imagen y la configuración, y ejecutar la función correspondiente
    def ejecutar_modo(self, modo_nombre: str, imagen_path: str, config: dict = None):
        modo_func = self.modos_soportados.get(modo_nombre.lower())
        if not modo_func:
            raise ValueError(f"El modo '{modo_nombre}' no está implementado en YOLO.")
        
        return modo_func(imagen_path, config or {})