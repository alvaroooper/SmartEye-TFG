import os
import cv2
from typing import Tuple, Dict, Any, List
from ultralytics import YOLO

# ==============================================================================
# CARGA DEL MOTOR DE INFERENCIA (SINGLETON SCOPE)
# ==============================================================================
# Se mantiene una única instancia del modelo en memoria para optimizar recursos.
# yolov8n es el modelo idóneo para tareas de segmentación en tiempo real.
_MODELO_YOLO_INSTANCE = YOLO('models/yolo/yolov8n.pt')

def procesar_recortes_personas(imagen_path: str, config: Dict[str, Any] = None, prefijo: str = "") -> Tuple[List[str], Dict[str, Any]]:
    """
    Ejecuta una inferencia selectiva para la localización y extracción de individuos.
    
    El proceso identifica sujetos (clase 0), segmenta la Región de Interés (ROI) y 
    aplica un redimensionamiento mediante interpolación cúbica para optimizar el 
    análisis en etapas posteriores del pipeline.

    Args:
        imagen_path (str): Ruta absoluta al activo físico de entrada.
        config (Dict, opcional): Hiperparámetros (conf, scale_factor).
        prefijo (str, opcional): Hash de trazabilidad para serialización de archivos.

    Returns:
        Tuple[List[str], Dict]: Vector de rutas de los recortes generados y telemetría JSON.
    """
    if config is None: 
        config = {}
    
    # 1. INGESTA Y VALIDACIÓN DE INTEGRIDAD
    imagen = cv2.imread(imagen_path)
    if imagen is None:
        raise ValueError(f"Fallo de integridad: Imposible leer el activo en {imagen_path}")

    # 2. CONFIGURACIÓN DE PARÁMETROS DE SEGMENTACIÓN
    confianza = config.get("conf", 0.30)
    # Factor de escalado para compensar la pérdida de resolución en recortes pequeños
    factor_escala = config.get("scale_factor", 3.0)
    
    # 3. INFERENCIA SELECTIVA (FILTRADO POR CLASE 'PERSON')
    # Se restringe la detección exclusivamente a la clase 0 (Humanos)
    resultados = _MODELO_YOLO_INSTANCE(imagen, conf=confianza, classes=[0])
    
    # Preparación del entorno de salida
    directorio = os.path.dirname(imagen_path)
    base_name = os.path.basename(imagen_path)
    str_prefijo = f"{prefijo}_" if prefijo else ""
    
    rutas_recortes = []
    objetos_detectados = []
    
    # 4. EXTRACCIÓN Y PROCESAMIENTO DE REGIONES DE INTERÉS (ROI)
    for i, caja in enumerate(resultados[0].boxes):
        # Obtención de coordenadas de la Bounding Box (formato xyxy)
        x1, y1, x2, y2 = map(int, caja.xyxy[0].tolist())
        conf_obj = round(caja.conf[0].item(), 4)
        
        # Ajuste de márgenes para prevenir desbordamiento de matriz
        x1, y1 = max(0, x1), max(0, y1)
        
        # Segmentación inicial del área detectada
        recorte_raw = imagen[y1:y2, x1:x2]
        
        # Validación de dimensionalidad para evitar procesar áreas nulas
        if recorte_raw.shape[0] == 0 or recorte_raw.shape[1] == 0:
            continue
            
        # 5. NORMALIZACIÓN Y RE-ESCALADO TÉCNICO
        # Se aplica interpolación cúbica (INTER_CUBIC) para el redimensionamiento,
        # lo que garantiza una mayor suavidad y detalle en la ampliación de la ROI.
        nuevo_ancho = int(recorte_raw.shape[1] * factor_escala)
        nuevo_alto = int(recorte_raw.shape[0] * factor_escala)
        
        recorte_ampliado = cv2.resize(
            recorte_raw, 
            (nuevo_ancho, nuevo_alto), 
            interpolation=cv2.INTER_CUBIC
        )
        
        # 6. PERSISTENCIA DE ACTIVOS SEGMENTADOS
        ruta_recorte = os.path.join(directorio, f"{str_prefijo}recorte_{i}_{base_name}")
        cv2.imwrite(ruta_recorte, recorte_ampliado)
        
        rutas_recortes.append(ruta_recorte)
        
        # Compilación de metadatos del activo extraído
        objetos_detectados.append({
            "id_instancia": i,
            "confianza": conf_obj,
            "archivo": os.path.basename(ruta_recorte),
            "resolucion_original": f"{recorte_raw.shape[1]}x{recorte_raw.shape[0]}",
            "resolucion_procesada": f"{nuevo_ancho}x{nuevo_alto}"
        })

    # Consolidación de resultados para auditoría
    datos_json = {
        "sujetos_localizados": len(rutas_recortes),
        "detalles": objetos_detectados
    }
    
    return rutas_recortes, datos_json