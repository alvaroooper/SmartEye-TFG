import cv2  # type: ignore
import mediapipe as mp # type: ignore
import os

# ==== CONFIGURACIÓN DE RUTAS ====
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # sube un nivel desde /src/
DATA_DIR = os.path.join(BASE_DIR, 'data')
DETECT_DIR = os.path.join(BASE_DIR, 'detect')

# Crea la carpeta detect/ si no existe
os.makedirs(DETECT_DIR, exist_ok=True)

# ==== CONFIGURACIÓN DE MEDIAPIPE ====
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

# ==== PROCESAR TODAS LAS IMÁGENES DE DATA ====
for filename in os.listdir(DATA_DIR):
    if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        image_path = os.path.join(DATA_DIR, filename)
        image = cv2.imread(image_path)

        if image is None:
            print(f"[ERROR] No se pudo leer: {filename}")
            continue

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        with mp_hands.Hands(static_image_mode=True, max_num_hands=2) as hands:
            results = hands.process(image_rgb)

            # Dibuja los resultados si hay detección
            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(
                        image,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS
                    )

        # Guardar el resultado
        output_path = os.path.join(DETECT_DIR, f"{os.path.splitext(filename)[0]}_result.jpg")
        cv2.imwrite(output_path, image)
        print(f"[OK] Resultado guardado en: {output_path}")

print("Procesamiento completado ✅")
