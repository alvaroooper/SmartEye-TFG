from ultralytics import YOLO # type: ignore
import torch # type: ignore
import cv2 # type: ignore

# Elegir dispositivo
device = 0 if torch.cuda.is_available() else "cpu"
print("cuda disponible:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0))

# Modelo
model = YOLO("yolov8n.pt")

# ===== OPCIÓN A: WEBCAM =====
cap = cv2.VideoCapture(0)  # cam por defecto

# ===== OPCIÓN B: VÍDEO =====
#cap = cv2.VideoCapture("data/video_prueba.mp4")

if not cap.isOpened():
    raise RuntimeError("No se pudo abrir la webcam o el archivo de vídeo.")

while True:
    ok, frame = cap.read()
    if not ok:
        break

    # Inferencia (usa device elegido)
    results = model.predict(source=frame, device=device, verbose=False)

    # Dibuja anotaciones
    annotated = results[0].plot()

    cv2.imshow("YOLO - q para salir", annotated)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
