# src/app/services/mock_detection_service.py
import io
from PIL import Image, ImageDraw  # type: ignore


def draw_mock_detection_box(image_bytes: bytes) -> bytes:
    """
    Recibe una imagen en bytes, dibuja una caja de detección simulada
    y devuelve la nueva imagen en formato PNG (también en bytes).
    """
    # Cargar imagen desde bytes
    image = Image.open(io.BytesIO(image_bytes))
    image = image.convert("RGB")  # nos aseguramos de tener RGB

    w, h = image.size

    # Definimos una caja "falsa" en el centro de la imagen (10% de margen)
    margin_x = int(w * 0.1)
    margin_y = int(h * 0.1)

    left = margin_x
    top = margin_y
    right = w - margin_x
    bottom = h - margin_y

    # Dibujar la caja
    draw = ImageDraw.Draw(image)
    draw.rectangle((left, top, right, bottom), outline="red", width=5)

    # Guardar resultado a bytes (PNG)
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)

    return output.getvalue()
