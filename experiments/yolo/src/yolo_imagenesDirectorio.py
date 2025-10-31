import os
from datetime import datetime
from ultralytics import YOLO # type: ignore

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
RUNS_DIR = os.path.join(ROOT_DIR, "runs")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(RUNS_DIR, exist_ok=True)

# extensiones aceptadas
valid_ext = {".jpg", ".jpeg", ".png", ".bmp"}

images = [
    os.path.join(DATA_DIR, f)
    for f in os.listdir(DATA_DIR)
    if os.path.splitext(f)[1].lower() in valid_ext
]

if not images:
    raise RuntimeError(f"No hay imágenes en {DATA_DIR}")

model = YOLO("yolov8n.pt")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
save_dir = os.path.join(RUNS_DIR, "detect", f"batch_{timestamp}")
os.makedirs(save_dir, exist_ok=True)

# le pasamos directamente la carpeta
results = model.predict(
    source=DATA_DIR,
    save=True,
    project=save_dir,
    name="",
    exist_ok=True
)

print(f"[OK] Procesadas {len(images)} imágenes. Salida en: {save_dir}")
