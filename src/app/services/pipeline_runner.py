import json
import os
from app.models import PipelineEtapa
from app.services.ai_factory import AIFactory

class PipelineRunner:
    @staticmethod
    def ejecutar_pipeline(id_pipeline: int, imagen_inicial: str, config_completa: dict):
        """
        Recupera las etapas del pipeline y las ejecuta secuencialmente.
        Soporta ramificación (una etapa puede generar varias imágenes de salida).
        """
        # 1. Obtener las etapas ordenadas por su campo 'orden'
        etapas = PipelineEtapa.query.filter_by(id_pipeline=id_pipeline).order_by(PipelineEtapa.orden).all()
        
        if not etapas:
            raise ValueError(f"El pipeline con ID {id_pipeline} no tiene etapas o no existe.")

        # Iniciamos con una lista que contiene solo la imagen original subida por el usuario
        rutas_actuales = [imagen_inicial]
        resultados = []

        # 2. Iterar sobre la secuencia de etapas
        for etapa in etapas:
            nombre_modelo = etapa.modelo.nombre
            nombre_modo = etapa.modo.nombre_modo
            
            print(f"--- Ejecutando etapa {etapa.orden}: {etapa.nombre} (Modelo={nombre_modelo}, Modo={nombre_modo}) ---")
            
            # --- CONFIGURACIÓN DINÁMICA ---
            # Extraemos del "Súper JSON" solo la parte que corresponde a esta etapa concreta
            config_etapa = config_completa.get(f"etapa_{etapa.orden}", {})
            
            # 3. Pedir el lanzador correspondiente al Factory 
            launcher = AIFactory.get_launcher(nombre_modelo)
            
            nuevas_rutas = []
            datos_etapa = []

            # 4. EJECUCIÓN RAMIFICADA
            # Ejecutamos el modelo sobre TODAS las imágenes que tengamos en este momento
            # (Si la etapa anterior fue de recortes, aquí procesaremos cada recorte individualmente)
            for ruta in rutas_actuales:
                # El launcher ahora recibe la config específica de la etapa
                res_rutas, json_res = launcher.ejecutar_modo(nombre_modo, ruta, config_etapa)
                
                # Si el modo devolvió una lista 
                if isinstance(res_rutas, list):
                    nuevas_rutas.extend(res_rutas)
                else:
                    # Si devolvió una sola ruta
                    nuevas_rutas.append(res_rutas)
                
                # Guardamos los datos JSON asociados a esta imagen concreta dentro de la etapa
                datos_etapa.append({
                    "origen": os.path.basename(ruta), 
                    "datos": json_res
                })

            # Actualizamos las rutas para la siguiente etapa del pipeline
            rutas_actuales = nuevas_rutas
            
            # 5. Acumular el resultado detallado de la etapa para el frontend 
            resultados.append({
                "etapa": etapa.orden,
                "nombre_etapa": etapa.nombre,
                "ia": nombre_modelo,
                "modo": nombre_modo,
                "imagenes": [os.path.basename(r) for r in rutas_actuales], # Lista de archivos generados
                "datos": datos_etapa # Lista de JSONs generados
            })

        # Retornamos las rutas de las últimas imágenes generadas y el historial completo
        return rutas_actuales, resultados