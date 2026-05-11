import os
from app.models import PipelineEtapa 
from app.services.ai_factory import AIFactory 

class PipelineRunner:
    """
    Motor de ejecución secuencial de pipelines. 
    Gestiona la lógica de encadenamiento entre distintas etapas de IA, permitiendo
    la ramificación de resultados (ej. una imagen que genera múltiples recortes).
    """

    @staticmethod
    def ejecutar_pipeline(id_pipeline: int, imagen_inicial: str, config_completa: dict, prefijo: str):
        """
        Orquesta la ejecución de las etapas de un pipeline sobre una imagen de entrada.
        
        Args:
            id_pipeline: Identificador único del flujo.
            imagen_inicial: Ruta absoluta al archivo original.
            config_completa: Diccionario con parámetros personalizados por etapa.
            prefijo: Identificador único para la nomenclatura de archivos generados.
            
        Returns:
            tuple: (Lista de rutas finales, Lista de resultados detallados por etapa).
        """
        # Recuperación de la secuencia lógica de etapas configurada en la BD
        etapas = PipelineEtapa.query.filter_by(id_pipeline=id_pipeline).order_by(PipelineEtapa.orden).all()
        
        if not etapas:
            raise ValueError(f"Configuración inválida: El pipeline {id_pipeline} no contiene etapas definidas.")

        # El flujo comienza siempre con el archivo original proporcionado por el usuario
        rutas_actuales = [imagen_inicial]
        resultados = []

        # Procesamiento secuencial del pipeline
        for etapa in etapas:
            nombre_modelo = etapa.modelo.nombre 
            nombre_modo = etapa.modo.nombre_modo
            
            # Recuperación de la configuración específica para esta etapa o uso de valores por defecto
            config_etapa = config_completa.get(f"etapa_{etapa.orden}", {})
            
            # Instanciación del launcher mediante el Factory Pattern
            launcher = AIFactory.get_launcher(nombre_modelo) 
            
            nuevas_rutas = []
            datos_etapa = []

            # 4. EJECUCIÓN RAMIFICADA: Se procesa cada imagen resultante de la etapa anterior
            for ruta in rutas_actuales:
                res_rutas, json_res = launcher.ejecutar_modo(nombre_modo, ruta, config_etapa, prefijo)
                
                # Gestión de salidas múltiples (listas) o simples (rutas únicas)
                if isinstance(res_rutas, list):
                    nuevas_rutas.extend(res_rutas)
                else:
                    if res_rutas: 
                        nuevas_rutas.append(res_rutas)
                
                # Agregación de metadatos técnicos generados por la IA para auditoría
                datos_etapa.append({
                    "origen": os.path.basename(ruta), 
                    "datos": json_res
                })

            # COMPROBACIÓN CRÍTICA DE FLUJO: Validación de existencia de detecciones
            # Si una etapa de detección (como YOLO) no localiza elementos, se detiene el pipeline
            # para evitar el procesamiento de datos nulos en etapas posteriores.
            if not nuevas_rutas:
                raise ValueError(
                    f"Análisis interrumpido: No se detectaron elementos (objetos/personas) "
                    f"procesables en la etapa '{etapa.nombre}'."
                )

            # Actualización del set de imágenes para la siguiente iteración
            rutas_actuales = nuevas_rutas
            
            # Compilación del objeto de resultado detallado para persistencia y frontend
            resultados.append({
                "etapa": etapa.orden,
                "nombre_etapa": etapa.nombre,
                "ia": nombre_modelo,
                "modo": nombre_modo,
                "imagenes": [os.path.basename(r) for r in rutas_actuales],
                "datos": datos_etapa
            })

        return rutas_actuales, resultados