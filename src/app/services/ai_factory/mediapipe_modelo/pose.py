import cv2
import mediapipe as mp
import os

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

def procesar_pose(imagen_path):
    imagen = cv2.imread(imagen_path)
    imagen_rgb = cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB)
    
    with mp_pose.Pose(static_image_mode=True) as pose:
        resultados = pose.process(imagen_rgb)
        if resultados.pose_landmarks:
            mp_drawing.draw_landmarks(imagen, resultados.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            
    ruta_salida = os.path.join(os.path.dirname(imagen_path), f"pose_{os.path.basename(imagen_path)}")
    cv2.imwrite(ruta_salida, imagen)
    return ruta_salida, {"pose_detectada": True if resultados.pose_landmarks else False}