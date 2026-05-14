from typing import Any
from .yolo.launcher import YoloLauncher
from .mediapipe_modelo.launcher import MediaPipeLauncher

class AIFactory:
    """
    Patrón de diseño Creacional (Factory Method).
    Centraliza la instanciación de los motores de inferencia de IA. 
    Permite desacoplar la lógica de orquestación (PipelineRunner) de las 
    implementaciones concretas y dependencias de cada framework subyacente.
    """

    @staticmethod
    def get_launcher(nombre_modelo: str) -> Any:
        """
        Resuelve e instancia dinámicamente el controlador (Launcher) adecuado 
        basándose en el identificador del modelo solicitado.
        
        Args:
            nombre_modelo (str): Identificador técnico del motor (ej. 'yolo', 'mediapipe').
            
        Returns:
            Any: Instancia operativa del controlador específico.
            
        Raises:
            ValueError: Excepción de resolución si el identificador no está catalogado.
        """
        if not nombre_modelo or not isinstance(nombre_modelo, str):
            raise ValueError("Excepción de resolución: El nombre del modelo debe ser una cadena válida.")
        # Sanitización de la entrada para evitar fallos por espacios o capitalización
        modelo = nombre_modelo.lower().strip()
        
        # Resolución estática de dependencias
        if modelo == "yolo":
            return YoloLauncher()
        elif modelo == "mediapipe":
            return MediaPipeLauncher()
        else:
            raise ValueError(
                f"Excepción de resolución: El motor de inferencia '{nombre_modelo}' "
                f"no está registrado en el catálogo del Factory."
            )