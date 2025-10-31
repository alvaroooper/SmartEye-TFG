from ultralytics import YOLO # type: ignore
import torch # type: ignore

# Info de GPU/CPU
print("torch:", torch.__version__)
print("cuda disponible:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0))

# Carga modelo (se descarga la 1ª vez)
model = YOLO("yolov8n.pt")

# Si hay GPU, usarla explícitamente (device=0); si no, CPU
device = 0 if torch.cuda.is_available() else "cpu"

# Predicción en imagen de ejemplo
results = model.predict(
    source="https://ultralytics.com/images/bus.jpg",
    device=device,
    save=True,   # guarda resultados en runs/
    show=True,   # intenta abrir ventana con la imagen anotada
)

print("OK: resultados guardados en carpeta 'runs'")
