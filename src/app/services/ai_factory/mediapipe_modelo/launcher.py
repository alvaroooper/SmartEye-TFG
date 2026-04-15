from app.services.ai_factory.interface import IALauncherBase
from .manos import procesar_manos
from .pose import procesar_pose

class MediaPipeLauncher(IALauncherBase):
    def __init__(self):
        self.modos_soportados = {
            "manos": procesar_manos,
            "pose": procesar_pose   # 2. Registrar el modo
        }

    def ejecutar_modo(self, modo_nombre: str, imagen_path: str):
        modo_func = self.modos_soportados.get(modo_nombre.lower())
        if not modo_func:
            raise ValueError(f"El modo '{modo_nombre}' no está implementado en MediaPipe.")
        
        return modo_func(imagen_path)