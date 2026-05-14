import os
from app.models import PipelineEtapa 
from app.services.ai_factory import AIFactory 

class PipelineRunner:
    """
    Motor de orquestación de inferencia (Inference Engine Orchestrator).
    Gestiona la ejecución secuencial de arquitecturas de IA, resolviendo dependencias 
    entre etapas, encadenamiento de activos físicos y ramificación topológica de 
    resultados (ej. segmentación 1:N de sujetos en una escena).
    """

    @staticmethod
    def ejecutar_pipeline(id_pipeline: int, imagen_inicial: str, config_completa: dict = None, prefijo: str = "") -> tuple[list[str], list[dict]]:
        """
        Controlador principal del ciclo de vida del flujo de trabajo (Workflow Lifecycle).
        
        Args:
            id_pipeline (int): Identificador unívoco del esquema de procesamiento.
            imagen_inicial (str): Ruta absoluta al activo físico de origen.
            config_completa (dict): Matriz de hiperparámetros inyectados por el cliente.
            prefijo (str): Hash o identificador de trazabilidad para serialización de artefactos.
            
        Returns:
            tuple[list[str], list[dict]]: Vector de activos terminales y telemetría de auditoría por etapa.
            
        Raises:
            ValueError: Excepción de integridad ante una configuración nula o interrupción por falta de ROI.
        """
        if config_completa is None:
            config_completa = {}
            
        # Validación de integridad del activo físico inicial
        if not imagen_inicial or not os.path.exists(imagen_inicial):
            raise ValueError(f"Excepción de integridad: El activo inicial '{imagen_inicial}' no existe o es inaccesible.")
        # 1. Extracción del esquema lógico de procesamiento desde la capa de persistencia
        etapas = PipelineEtapa.query.filter_by(id_pipeline=id_pipeline).order_by(PipelineEtapa.orden).all()
        
        if not etapas:
            raise ValueError(f"Excepción de integridad: La definición del pipeline {id_pipeline} carece de nodos operativos.")

        # 2. Inicialización del vector de activos (Asset Vector) de la capa base
        rutas_actuales = [imagen_inicial]
        resultados = []

        # 3. Evaluación secuencial de la cadena de inferencia
        for etapa in etapas:
            nombre_modelo = etapa.modelo.nombre 
            nombre_modo = etapa.modo.nombre_modo
            
            # Inyección de parámetros específicos del nodo en curso
            config_etapa = config_completa.get(f"etapa_{etapa.orden}", {})
            
            # Resolución del motor subyacente mediante el patrón Abstract Factory
            launcher = AIFactory.get_launcher(nombre_modelo) 
            
            nuevas_rutas = []
            datos_etapa = []

            # 4. Procesamiento ramificado (Branching Execution)
            # Iteración sobre cada activo generado en la capa computacional previa
            for ruta in rutas_actuales:
                res_rutas, json_res = launcher.ejecutar_modo(nombre_modo, ruta, config_etapa, prefijo)
                
                # Normalización de salidas (Manejo dinámico de respuestas 1:1 o 1:N)
                if isinstance(res_rutas, list):
                    nuevas_rutas.extend(res_rutas)
                elif res_rutas: 
                    nuevas_rutas.append(res_rutas)
                
                # Consolidación de telemetría y metadatos JSON para el log de la etapa
                datos_etapa.append({
                    "origen": os.path.basename(ruta), 
                    "datos": json_res
                })

            # 5. Regla de parada temprana (Early Stopping Criteria)
            # Interrumpe el pipeline completo si un modelo de detección (ej. YOLO) 
            # no localiza Regiones de Interés (ROI), mitigando ciclos computacionales nulos.
            if not nuevas_rutas:
                raise ValueError(
                    f"Análisis interrumpido: Ausencia de elementos procesables (ROI) "
                    f"en la salida de la etapa '{etapa.nombre}'."
                )

            # 6. Propagación de estado hacia la subsecuente capa de inferencia
            rutas_actuales = nuevas_rutas
            
            # 7. Empaquetado estructurado para serialización de respuesta final
            resultados.append({
                "etapa": etapa.orden,
                "nombre_etapa": etapa.nombre,
                "ia": nombre_modelo,
                "modo": nombre_modo,
                "imagenes": [os.path.basename(r) for r in rutas_actuales],
                "datos": datos_etapa
            })

        return rutas_actuales, resultados