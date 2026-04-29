import json
import os
from app.models import PipelineEtapa 
from app.services.ai_factory import AIFactory 

class PipelineRunner:
    @staticmethod
    def ejecutar_pipeline(id_pipeline: int, imagen_inicial: str, config_completa: dict, prefijo: str):
        """
        Recupera las etapas del pipeline y las ejecuta secuencialmente.
        Soporta ramificación y el uso de un prefijo único para el guardado de archivos.
        """
        # 1. Obtener las etapas ordenadas por su campo 'orden'
        etapas = PipelineEtapa.query.filter_by(id_pipeline=id_pipeline).order_by(PipelineEtapa.orden).all()
        
        if not etapas:
            raise ValueError(f"El pipeline con ID {id_pipeline} no tiene etapas o no existe.")

        # Iniciamos con una lista que contiene solo la imagen original
        rutas_actuales = [imagen_inicial]
        resultados = []

        # 2. Iterar sobre la secuencia de etapas
        for etapa in etapas:
            nombre_modelo = etapa.modelo.nombre 
            nombre_modo = etapa.modo.nombre_modo
            
            print(f"--- Ejecutando etapa {etapa.orden}: {etapa.nombre} (Modelo={nombre_modelo}, Modo={nombre_modo}) ---")
            
            # --- CONFIGURACIÓN DINÁMICA ---
            # Extraemos la sub-configuración correspondiente a esta etapa
            config_etapa = config_completa.get(f"etapa_{etapa.orden}", {})
            
            # 3. Pedir el lanzador correspondiente al Factory 
            launcher = AIFactory.get_launcher(nombre_modelo) 
            
            nuevas_rutas = []
            datos_etapa = []

            # 4. EJECUCIÓN RAMIFICADA
            for ruta in rutas_actuales:
                # --- NUEVO: Pasamos el 'prefijo' al launcher para que las IAs lo usen al guardar ---
                res_rutas, json_res = launcher.ejecutar_modo(nombre_modo, ruta, config_etapa, prefijo)
                
                if isinstance(res_rutas, list):
                    nuevas_rutas.extend(res_rutas)
                else:
                    nuevas_rutas.append(res_rutas)
                
                datos_etapa.append({
                    "origen": os.path.basename(ruta), 
                    "datos": json_res
                })

            rutas_actuales = nuevas_rutas
            
            # 5. Acumular el resultado detallado para el frontend 
            resultados.append({
                "etapa": etapa.orden,
                "nombre_etapa": etapa.nombre,
                "ia": nombre_modelo,
                "modo": nombre_modo,
                "imagenes": [os.path.basename(r) for r in rutas_actuales],
                "datos": datos_etapa
            })

        return rutas_actuales, resultados