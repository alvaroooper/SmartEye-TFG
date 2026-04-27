import cv2
import mediapipe as mp
import os

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

def procesar_pose(imagen_path, config=None):
    # Si no llega ninguna configuración, usamos un diccionario vacío
    if config is None:
        config = {}
        
    print(f"[MediaPipe] Ejecutando pose en: {imagen_path} con config: {config}")
    
    imagen = cv2.imread(imagen_path)
    if imagen is None:
        raise ValueError(f"No se pudo leer la imagen: {imagen_path}")
        
    imagen_rgb = cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB)
    
    # Extraer valores del JSON (con valores por defecto)
    complexidad = config.get("model_complexity", 1)
    min_conf = config.get("min_detection_confidence", 0.5)
    
    # --- NUEVO: Estructura del JSON mejorada ---
    datos_json = {
        "pose_detectada": False, 
        "total_puntos": 0,
        "detalles": []
    }
    
    with mp_pose.Pose(
        static_image_mode=True,
        model_complexity=complexidad,
        min_detection_confidence=min_conf
    ) as pose:
        
        resultados = pose.process(imagen_rgb)
        
        if resultados.pose_landmarks:
            datos_json["pose_detectada"] = True
            
            # Extraer los 33 puntos clave (landmarks) y su información
            puntos = resultados.pose_landmarks.landmark
            datos_json["total_puntos"] = len(puntos)
            
            for idx, landmark in enumerate(puntos):
                # mp_pose.PoseLandmark(idx).name da el nombre real (ej: 'LEFT_SHOULDER')
                nombre_parte = mp_pose.PoseLandmark(idx).name
                
                # Añadimos la info de cada punto redondeando los decimales para no saturar el JSON
                datos_json["detalles"].append({
                    "id": idx,
                    "parte_cuerpo": nombre_parte,
                    "coordenadas": {
                        "x": round(landmark.x, 4), # Posición horizontal (0 a 1)
                        "y": round(landmark.y, 4), # Posición vertical (0 a 1)
                        "z": round(landmark.z, 4)  # Profundidad respecto a la cámara
                    },
                    "visibilidad": round(landmark.visibility, 2) # Nivel de certeza de que el punto se ve
                })
            
            # Dibujar los puntos y las conexiones sobre la imagen
            mp_drawing.draw_landmarks(
                imagen, 
                resultados.pose_landmarks, 
                mp_pose.POSE_CONNECTIONS
            )
            
    # Guardar la imagen
    directorio = os.path.dirname(imagen_path)
    nombre_archivo = os.path.basename(imagen_path)
    ruta_salida = os.path.join(directorio, f"pose_{nombre_archivo}")
    
    cv2.imwrite(ruta_salida, imagen)
    
    return ruta_salida, datos_json