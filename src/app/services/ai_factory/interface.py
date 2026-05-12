from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any, Union, List

class IALauncherBase(ABC):
    """
    Clase Base Abstracta (Interface) que establece el contrato operativo para los 
    controladores de IA. 
    
    Su implementación garantiza el desacoplamiento entre el motor de ejecución 
    (PipelineRunner) y los frameworks específicos de visión artificial, permitiendo 
    una arquitectura extensible y modular.
    """

    @abstractmethod
    def ejecutar_modo(self, 
                      modo_nombre: str, 
                      imagen_path: str, 
                      config: Dict[str, Any] = None, 
                      prefijo: str = "") -> Tuple[Union[str, List[str]], Dict[str, Any]]:        
        """
        Ejecuta un algoritmo de inferencia específico sobre un activo físico de entrada.

        Args:
            modo_nombre (str): Identificador técnico de la tarea (ej. 'pose', 'deteccion').
            imagen_path (str): Ruta absoluta al archivo de imagen en el servidor.
            config (Dict, opcional): Diccionario de hiperparámetros y configuración del modelo.
            prefijo (str, opcional): Cadena de trazabilidad para la nomenclatura de archivos de salida.

        Returns:
            Tuple[Union[str, List[str]], Dict[str, Any]]: Una tupla que contiene:
                - La ruta o lista de rutas de los activos generados (imágenes/recortes).
                - Un diccionario con el esquema de metadatos y resultados del análisis (JSON).
        """
        pass