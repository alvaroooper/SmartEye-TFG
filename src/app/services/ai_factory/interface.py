from abc import ABC, abstractmethod

class IALauncherBase(ABC):
    @abstractmethod
    def ejecutar_modo(self, modo_nombre: str, imagen_path: str, config: dict = None, prefijo: str = ""):        
        """
        Ejecuta un modo específico de la IA sobre una imagen aplicando una configuración.
        Debe retornar una tupla: (ruta_imagen_resultado, diccionario_datos_json)
        """
        pass