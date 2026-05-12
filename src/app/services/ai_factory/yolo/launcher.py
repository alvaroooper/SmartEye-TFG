from typing import Tuple, Dict, Any, Union, List, Callable
from app.services.ai_factory.interface import IALauncherBase
from .deteccion import procesar_deteccion
from .recortes import procesar_recortes_personas

class YoloLauncher(IALauncherBase):
    """
    Implementación concreta del controlador para el ecosistema YOLO (You Only Look Once).
    
    Esta clase actúa como un despachador dinámico que mapea los requisitos 
    operativos del pipeline con los algoritmos específicos de visión artificial 
    basados en redes neuronales convolucionales de última generación.
    """

    def __init__(self):
        """
        Inicialización del catálogo de estrategias de inferencia.
        Establece el mapeo entre los identificadores lógicos de la persistencia 
        y las funciones de procesamiento especializadas.
        """
        self._task_map: Dict[str, Callable] = {
            "deteccion": procesar_deteccion,
            "recortes_personas": procesar_recortes_personas
        }

    def ejecutar_modo(self, 
                      modo_nombre: str, 
                      imagen_path: str, 
                      config: Dict[str, Any] = None, 
                      prefijo: str = "") -> Tuple[Union[str, List[str]], Dict[str, Any]]:
        """
        Ejecuta la inferencia mediante el motor YOLO seleccionado.

        Args:
            modo_nombre (str): Identificador de la tarea (deteccion, recortes_personas).
            imagen_path (str): Ruta absoluta al activo físico de entrada.
            config (Dict, opcional): Matriz de hiperparámetros de configuración.
            prefijo (str, opcional): Hash de trazabilidad para la nomenclatura de salida.

        Returns:
            Tuple: Ruta(s) de los activos generados y esquema de metadatos del análisis.

        Raises:
            ValueError: Ante una solicitud de un modo operativo no registrado.
        """
        # Resolución dinámica de la rutina de inferencia
        ejecutor = self._task_map.get(modo_nombre.lower().strip())
        
        if not ejecutor:
            raise ValueError(
                f"Excepción de resolución: El modo operativo '{modo_nombre}' no está "
                f"implementado dentro del subsistema YOLO."
            )
        
        # Invocación de la rutina con inyección de parámetros de configuración
        return ejecutor(imagen_path, config or {}, prefijo)