import os
import cv2
from ultralytics import YOLO

modelo_yolo = YOLO('yolov8n.pt')

def procesar_recortes_personas(imagen_path, config=None):
    if config is None: config = {}
    
    imagen = cv2.imread(imagen_path)
    if imagen is None:
        raise ValueError(f"No se pudo leer la imagen: {imagen_path}")

    confianza = config.get("conf", 0.30)
    # Factor de escala para hacer el recorte más grande
    # Por defecto multiplicamos el tamaño por 3
    factor_escala = config.get("scale_factor", 3.0) 
    
    # classes=[0] obliga a YOLO a buscar SOLO personas
    resultados = modelo_yolo(imagen, conf=confianza, classes=[0])
    
    directorio = os.path.dirname(imagen_path)
    base_name = os.path.basename(imagen_path)
    
    rutas_recortes = []
    objetos_detectados = []
    
    for i, caja in enumerate(resultados[0].boxes):
        # Obtener coordenadas de la caja (bounding box)
        x1, y1, x2, y2 = map(int, caja.xyxy[0].tolist())
        conf_obj = round(caja.conf[0].item(), 2)
        
        # Evitar recortes inválidos si se salen de los márgenes
        x1, y1 = max(0, x1), max(0, y1)
        
        # Hacer el recorte original
        recorte = imagen[y1:y2, x1:x2]
        
        # Ignorar si el recorte es demasiado pequeño o vacío
        if recorte.shape[0] == 0 or recorte.shape[1] == 0:
            continue
            
        # --- LA MAGIA DEL ESCALADO ---
        # Calculamos las nuevas dimensiones
        nuevo_ancho = int(recorte.shape[1] * factor_escala)
        nuevo_alto = int(recorte.shape[0] * factor_escala)
        
        # Redimensionamos usando interpolación cúbica (ideal para hacer imágenes más grandes sin pixelar tanto)
        recorte_ampliado = cv2.resize(recorte, (nuevo_ancho, nuevo_alto), interpolation=cv2.INTER_CUBIC)
        # -----------------------------
        
        ruta_recorte = os.path.join(directorio, f"recorte_{i}_{base_name}")
        
        # Guardamos la imagen AMPLIADA en lugar de la pequeña
        cv2.imwrite(ruta_recorte, recorte_ampliado)
        
        rutas_recortes.append(ruta_recorte)
        objetos_detectados.append({
            "id_persona": i,
            "confianza": conf_obj,
            "archivo": os.path.basename(ruta_recorte),
            "dimensiones_originales": f"{recorte.shape[1]}x{recorte.shape[0]}",
            "dimensiones_ampliadas": f"{nuevo_ancho}x{nuevo_alto}"
        })

    datos_json = {
        "personas_encontradas": len(rutas_recortes),
        "detalles": objetos_detectados
    }
    
    return rutas_recortes, datos_json