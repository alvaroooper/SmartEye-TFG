import os
from datetime import datetime
from ultralytics import YOLO # type: ignore

# carpeta raíz del repo (TFG/TFG)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# ROOT_DIR ahora es ...\experiments\pruebas_yolo

DATA_DIR = os.path.join(ROOT_DIR, "data")      # ...\experiments\pruebas_yolo\data
RUNS_DIR = os.path.join(ROOT_DIR, "runs")      # ...\experiments\pruebas_yolo\runs

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(RUNS_DIR, exist_ok=True)

# 1) imagen a probar
IMAGE_NAME = "coche.png"   # <-- nombre imagen a procesar
image_path = os.path.join(DATA_DIR, IMAGE_NAME)

if not os.path.isfile(image_path):
    raise FileNotFoundError(f"No existe la imagen en data/: {image_path}")

# 2) carga modelo
model = YOLO("yolov8n.pt")   # modelo simple, cambiar a 'yolov8s.pt' para más precisión

# 3) carpeta de salida con timestamp dentro de runs
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
save_dir = os.path.join(RUNS_DIR, "detect", f"pred_{timestamp}")
os.makedirs(save_dir, exist_ok=True)

# 4) inferencia
results = model.predict(
    source=image_path,
    save=True,
    project=save_dir,
    name="",
    exist_ok=True
)

print(f"[OK] Imagen procesada. Resultado en: {save_dir}")
