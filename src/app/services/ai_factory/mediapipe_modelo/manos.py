import os
import cv2
import mediapipe as mp

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

def procesar_manos(imagen_path):
    print(f"[MediaPipe] Ejecutando detección de manos en: {imagen_path}")
    
    # 1. Leer imagen con OpenCV
    imagen = cv2.imread(imagen_path)
    if imagen is None:
        raise ValueError(f"No se pudo leer la imagen: {imagen_path}")
    # MediaPipe necesita la imagen en formato RGB, pero OpenCV la lee en BGR
    imagen_rgb = cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB)
    
    datos_json = {"manos_detectadas": 0, "detalles": []}

    # 2. Configurar y ejecutar el modelo
    with mp_hands.Hands(
        static_image_mode=True, 
        max_num_hands=2, 
        min_detection_confidence=0.5
    ) as hands:
        
        resultados = hands.process(imagen_rgb)
        
        # 3. Procesar resultados si se encontró alguna mano
        if resultados.multi_hand_landmarks:
            datos_json["manos_detectadas"] = len(resultados.multi_hand_landmarks)
            
            for idx, hand_landmarks in enumerate(resultados.multi_hand_landmarks):
                # Extraer si es mano izquierda o derecha (si está disponible)
                if resultados.multi_handedness:
                    mano_info = resultados.multi_handedness[idx].classification[0]
                    etiqueta = mano_info.label
                    confianza = round(mano_info.score, 2)
                else:
                    etiqueta = "Desconocida"
                    confianza = 0.0
                    
                datos_json["detalles"].append({
                    "tipo": etiqueta, 
                    "confianza": confianza
                })
                
                # 4. Dibujar los puntos sobre la imagen original (en BGR)
                mp_drawing.draw_landmarks(
                    imagen, 
                    hand_landmarks, 
                    mp_hands.HAND_CONNECTIONS
                )

    # 5. Guardar la nueva imagen procesada
    directorio = os.path.dirname(imagen_path)
    nombre_archivo = os.path.basename(imagen_path)
    ruta_salida = os.path.join(directorio, f"mp_{nombre_archivo}")
    
    cv2.imwrite(ruta_salida, imagen)
    
    return ruta_salida, datos_json