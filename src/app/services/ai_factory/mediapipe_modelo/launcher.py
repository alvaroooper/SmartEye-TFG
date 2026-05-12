from typing import Tuple, Dict, Any, Union, List, Callable
from app.services.ai_factory.interface import IALauncherBase
from .manos import procesar_manos
from .pose import procesar_pose

class MediaPipeLauncher(IALauncherBase):
    """
    Implementación concreta del controlador para el ecosistema MediaPipe.
    Actúa como un despachador (Dispatcher) que mapea los identificadores lógicos 
    de la base de datos con los algoritmos específicos de procesamiento de landmarks.
    """

    def __init__(self):
        """
        Inicialización del catálogo de capacidades operativas.
        Define el mapeo entre etiquetas de modo y sus correspondientes 
        rutinas de procesamiento de visión artificial.
        """
        self._estrategias: Dict[str, Callable] = {
            "manos": procesar_manos,
            "pose": procesar_pose
        }

    def ejecutar_modo(self, 
                      modo_nombre: str, 
                      imagen_path: str, 
                      config: Dict[str, Any] = None, 
                      prefijo: str = "") -> Tuple[Union[str, List[str]], Dict[str, Any]]:
        """
        Ejecuta la inferencia mediante el motor MediaPipe seleccionado.

        Args:
            modo_nombre (str): Identificador del algoritmo (ej. 'manos', 'pose').
            imagen_path (str): Ruta al activo físico de entrada.
            config (Dict, opcional): Hiperparámetros de configuración del modelo.
            prefijo (str, opcional): Hash de trazabilidad para la salida.

        Returns:
            Tuple: Activos generados y metadatos del análisis esquelético/palmar.

        Raises:
            ValueError: Si el modo solicitado no se encuentra registrado en el despachador.
        """
        # Resolución dinámica de la rutina de procesamiento
        ejecutor = self._estrategias.get(modo_nombre.lower())
        
        if not ejecutor:
            raise ValueError(
                f"Excepción de capacidad: El algoritmo '{modo_nombre}' no está "
                f"implementado o registrado para el motor MediaPipe."
            )
        
        # Ejecución de la rutina con inyección de parámetros
        return ejecutor(imagen_path, config or {}, prefijo)