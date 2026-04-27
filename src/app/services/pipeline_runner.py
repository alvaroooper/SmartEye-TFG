import json
import os
from app.models import PipelineEtapa
from app.services.ai_factory import AIFactory

class PipelineRunner:
    @staticmethod
    def ejecutar_pipeline(id_pipeline: int, imagen_inicial: str):
        etapas = PipelineEtapa.query.filter_by(id_pipeline=id_pipeline).order_by(PipelineEtapa.orden).all()
        if not etapas: raise ValueError(f"El pipeline con ID {id_pipeline} no tiene etapas.")

        # Empezamos con una lista que tiene solo la imagen original
        rutas_actuales = [imagen_inicial]
        resultados = []

        for etapa in etapas:
            nombre_modelo = etapa.modelo.nombre       
            nombre_modo = etapa.modo.nombre_modo      
            
            config_dict = {}
            ruta_config = etapa.modo.config_predeterminada
            if ruta_config and os.path.exists(ruta_config):
                try:
                    with open(ruta_config, 'r', encoding='utf-8') as f:
                        config_dict = json.load(f)
                except Exception as e:
                    pass

            launcher = AIFactory.get_launcher(nombre_modelo)
            
            nuevas_rutas = []
            datos_etapa = []

            # Ejecutamos el modelo sobre TODAS las imágenes actuales
            for ruta in rutas_actuales:
                res_rutas, json_res = launcher.ejecutar_modo(nombre_modo, ruta, config_dict)
                
                # Si el modo devolvió una lista
                if isinstance(res_rutas, list):
                    nuevas_rutas.extend(res_rutas)
                else:
                    # Si devolvió una sola imagen la añadimos
                    nuevas_rutas.append(res_rutas)
                    
                datos_etapa.append({"origen": os.path.basename(ruta), "datos": json_res})

            # Las rutas resultantes serán la entrada para la siguiente etapa
            rutas_actuales = nuevas_rutas
            
            resultados.append({
                "etapa": etapa.orden,
                "nombre_etapa": etapa.nombre,
                "ia": nombre_modelo,
                "modo": nombre_modo,
                "imagenes": [os.path.basename(r) for r in rutas_actuales], # Guardamos todas
                "datos": datos_etapa
            })

        return rutas_actuales, resultados