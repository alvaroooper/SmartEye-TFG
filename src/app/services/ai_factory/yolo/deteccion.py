import os
from typing import Tuple, Dict, Any
from ultralytics import YOLO

# ==============================================================================
# CARGA DEL MODELO PRE-ENTRENADO (SINGLETON PATTERN)
# ==============================================================================
# Se instancia el modelo en el scope global para garantizar su permanencia en 
# memoria volátil (RAM), evitando latencias críticas por recarga en cada petición.
# Se utiliza el modelo yolov8n (Nano) para optimizar el balance precisión/rendimiento.
_MODELO_YOLO_INSTANCE = YOLO('models/yolo/yolov8n.pt')



def procesar_deteccion(imagen_path: str, config: Dict[str, Any] = None, prefijo: str = "") -> Tuple[str, Dict[str, Any]]:
    """
    Ejecuta una inferencia multiclase basada en redes neuronales convolucionales (YOLOv8).
    
    El proceso identifica, localiza y clasifica objetos dentro de un espacio 
    bidimensional, aplicando filtros de confianza y algoritmos de Supresión 
    de No Máximos (NMS) según la configuración inyectada.

    Args:
        imagen_path (str): Ruta absoluta al activo físico de entrada.
        config (Dict, opcional): Hiperparámetros de inferencia (conf, iou, imgsz).
        prefijo (str, opcional): Identificador de trazabilidad para la nomenclatura de salida.

    Returns:
        Tuple[str, Dict]: Ruta del activo renderizado y esquema de metadatos detectados.
    """
    if config is None:
        config = {}
        
    # 1. VALIDACIÓN DE INTEGRIDAD DEL ACTIVO
    if not os.path.exists(imagen_path):
        raise ValueError(f"Fallo de integridad: No se localizó el archivo en la ruta {imagen_path}")

    # 2. EXTRACCIÓN Y TIPADO DE HIPERPARÁMETROS DE CONTROL
    # conf: Umbral mínimo de confianza para considerar válida una predicción.
    # iou: Intersection Over Union; umbral para el filtrado de solapamiento (NMS).
    # imgsz: Resolución de entrada para el redimensionamiento del tensor.
    try:
        confianza = float(config.get("conf", 0.25))
        iou_val = float(config.get("iou", 0.45))
        img_size = int(config.get("imgsz", 640))
    except (ValueError, TypeError):
        raise ValueError("Excepción de tipo: Los hiperparámetros de YOLO (conf, iou, imgsz) deben ser numéricos.")
    
    # 3. EJECUCIÓN DEL MOTOR DE INFERENCIA
    # El motor procesa la imagen y genera un objeto Results de Ultralytics.
    resultados = _MODELO_YOLO_INSTANCE(
        imagen_path, 
        conf=confianza, 
        iou=iou_val, 
        imgsz=img_size
    )
    
    # Obtención de la primera instancia de resultados (procesamiento de activo único)
    resultado = resultados[0]
    
    # 4. GESTIÓN DE NOMENCLATURA Y PERSISTENCIA
    directorio = os.path.dirname(imagen_path)
    nombre_archivo = os.path.basename(imagen_path)
    str_prefijo = f"{prefijo}_" if prefijo else ""
    ruta_salida = os.path.join(directorio, f"{str_prefijo}deteccion_{nombre_archivo}")
    
    # Renderizado automático de Bounding Boxes y etiquetas sobre el activo resultante
    resultado.save(filename=ruta_salida)
    
    if not os.path.exists(ruta_salida):
        raise IOError(f"Fallo crítico de sistema: Imposible persistir el activo de detección en disco: {ruta_salida}")
    # 5. SERIALIZACIÓN DE METADATOS PARA AUDITORÍA
    objetos_detectados = []
    for caja in resultado.boxes:
        clase_id = int(caja.cls[0].item())
        nombre_clase = _MODELO_YOLO_INSTANCE.names[clase_id]
        confianza_obj = round(caja.conf[0].item(), 4) # Mayor precisión decimal para análisis técnico
        
        objetos_detectados.append({
            "clase": nombre_clase,
            "confianza": confianza_obj
        })
        
    datos_json = {
        "total_objetos": len(objetos_detectados), 
        "detalles": objetos_detectados 
    }
    
    return ruta_salida, datos_json