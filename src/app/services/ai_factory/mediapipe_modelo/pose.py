import os
import cv2
import mediapipe as mp
from typing import Tuple, Dict, Any

# ==============================================================================
# CONFIGURACIÓN DE COMPONENTES MEDIAPIPE
# ==============================================================================
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

def procesar_pose(imagen_path: str, config: Dict[str, Any] = None, prefijo: str = "") -> Tuple[str, Dict[str, Any]]:
    """
    Ejecuta la estimación de la estructura esquelética humana mediante MediaPipe Pose.
    
    El algoritmo realiza una inferencia tridimensional (X, Y, Z) de 33 puntos clave
    basada en un modelo de regresión de landmarks, permitiendo el análisis de 
    orientación y postura espacial del sujeto.

    Args:
        imagen_path (str): Ruta absoluta al activo físico de entrada.
        config (Dict, opcional): Hiperparámetros (model_complexity, min_detection_confidence).
        prefijo (str, opcional): Identificador de trazabilidad para la nomenclatura de salida.

    Returns:
        Tuple[str, Dict]: Ruta del activo renderizado y esquema de metadatos espaciales.
    """
    if config is None:
        config = {}
    
    try:
        complejidad = int(config.get("model_complexity", 1)) 
        min_conf = float(config.get("min_detection_confidence", 0.5))
    except (ValueError, TypeError):
        raise ValueError("Excepción de tipo: Los hiperparámetros de Pose deben ser numéricos.")
    
    # 1. INGESTA Y PREPROCESAMIENTO
    imagen = cv2.imread(imagen_path)
    if imagen is None:
        raise ValueError(f"Fallo de integridad: No se pudo leer el activo en {imagen_path}")
        
    # Conversión al espacio de color RGB para compatibilidad con el motor de inferencia
    imagen_rgb = cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB)
    
    # Inicialización del esquema de telemetría de salida
    datos_json = {
        "pose_detectada": False, 
        "total_puntos": 0,
        "detalles": []
    }
    
    # 2. EJECUCIÓN DEL MOTOR DE INFERENCIA
    with mp_pose.Pose(
        static_image_mode=True,
        model_complexity=complejidad,
        min_detection_confidence=min_conf
    ) as pose:
        
        resultados = pose.process(imagen_rgb)
        
        # 3. EXTRACCIÓN Y SERIALIZACIÓN DE METADATOS ESPACIALES
        if resultados.pose_landmarks:
            datos_json["pose_detectada"] = True
            
            # Procesamiento de la topología esquelética (33 landmarks estándar)
            puntos = resultados.pose_landmarks.landmark
            datos_json["total_puntos"] = len(puntos)
            
            for idx, landmark in enumerate(puntos):
                # Resolución del identificador anatómico del punto clave
                nombre_parte = mp_pose.PoseLandmark(idx).name
                
                # Serialización de coordenadas normalizadas y métricas de visibilidad
                datos_json["detalles"].append({
                    "id": idx,
                    "parte_cuerpo": nombre_parte,
                    "coordenadas": {
                        "x": round(landmark.x, 4),      # Posición relativa horizontal
                        "y": round(landmark.y, 4),      # Posición relativa vertical
                        "z": round(landmark.z, 4)       # Profundidad relativa (Z-depth)
                    },
                    "visibilidad": round(landmark.visibility, 2) # Umbral de certeza del landmark
                })
            
            # 4. RENDERIZADO DE LA RED ESQUELÉTICA (POST-PROCESAMIENTO)
            # Proyecta las conexiones y landmarks sobre la imagen original.
            mp_drawing.draw_landmarks(
                imagen, 
                resultados.pose_landmarks, 
                mp_pose.POSE_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(255, 0, 0), thickness=2, circle_radius=2), # Puntos en azul
                mp_drawing.DrawingSpec(color=(0, 255, 255), thickness=2)                  # Conexiones en cian
            )
            
    # 5. PERSISTENCIA DEL ACTIVO RESULTANTE
    directorio = os.path.dirname(imagen_path)
    nombre_archivo = os.path.basename(imagen_path)
    str_prefijo = f"{prefijo}_" if prefijo else ""
    ruta_salida = os.path.join(directorio, f"{str_prefijo}mp_pose_{nombre_archivo}")
    
    exito_escritura = cv2.imwrite(ruta_salida, imagen)
    if not exito_escritura:
        raise IOError(f"Fallo crítico de sistema: Imposible persistir el activo esquelético en disco: {ruta_salida}")
    
    return ruta_salida, datos_json