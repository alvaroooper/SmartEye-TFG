from app.services.ai_factory.interface import IALauncherBase
from .manos import procesar_manos
from .pose import procesar_pose

class MediaPipeLauncher(IALauncherBase):
    # Mapear el string procetente de la BD a la función real
    def __init__(self):
        self.modos_soportados = {
            "manos": procesar_manos,
            "pose": procesar_pose
        }

    # Recibir el nombre del modo, la imagen y la configuración, y ejecutar la función correspondiente
    def ejecutar_modo(self, modo_nombre: str, imagen_path: str, config: dict = None, prefijo: str = ""):
        modo_func = self.modos_soportados.get(modo_nombre.lower())
        if not modo_func:
            raise ValueError(f"El modo '{modo_nombre}' no está implementado en MediaPipe.")
        
        return modo_func(imagen_path, config or {}, prefijo)