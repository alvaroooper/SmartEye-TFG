import os
from ultralytics import YOLO

# Instanciamos el modelo fuera de la función para que no se recargue en cada petición.
# Al usar 'yolov8n.pt' (nano), Ultralytics descargará el archivo de pesos 
# automáticamente la primera vez que se ejecute.
modelo_yolo = YOLO('yolov8n.pt')

def procesar_deteccion(imagen_path, config=None, prefijo=""):
    # Si no llega ninguna configuración, usamos un diccionario vacío
    if config is None:
        config = {}
        
    print(f"[YOLO] Ejecutando detección en: {imagen_path} con config: {config}")
    
    # Validación de seguridad: comprobamos que el archivo realmente exista antes de pasarlo a YOLO
    if not os.path.exists(imagen_path):
        raise ValueError(f"No se encontró la imagen en la ruta: {imagen_path}")

    # EXTRAER VALORES DEL JSON (con valores óptimos por defecto si no existen)
    confianza = config.get("conf", 0.25)
    iou_val = config.get("iou", 0.45)
    img_size = config.get("imgsz", 640)
    
    # 1. Ejecutar inferencia pasándole los parámetros dinámicos de configuración
    resultados = modelo_yolo(
        imagen_path, 
        conf=confianza, 
        iou=iou_val, 
        imgsz=img_size
    )
    
    # YOLO devuelve una lista (por si le pasas un lote de imágenes). 
    # Como le pasamos una sola, cogemos la primera.
    resultado = resultados[0]
    
    # 2. Generar ruta de salida
    directorio = os.path.dirname(imagen_path)
    nombre_archivo = os.path.basename(imagen_path)
    str_prefijo = f"{prefijo}_" if prefijo else ""
    ruta_salida = os.path.join(directorio, f"{str_prefijo}deteccion_{nombre_archivo}")
    
    # 3. Guardar la imagen con las predicciones dibujadas sobre ella. El método save de Ultralytics se encarga de dibujar las cajas y etiquetas automáticamente.
    resultado.save(filename=ruta_salida)
    
    # 4. Extraer la información para el JSON
    objetos_detectados = []
    for caja in resultado.boxes:
        clase_id = int(caja.cls[0].item()) 
        nombre_clase = modelo_yolo.names[clase_id] # Pasa de ID (ej. 0) a Texto (ej. "person")
        confianza_obj = round(caja.conf[0].item(), 2) 
        
        objetos_detectados.append({
            "clase": nombre_clase,
            "confianza": confianza_obj
        })
        
    datos_json = {
        "total_objetos": len(objetos_detectados), 
        "detalles": objetos_detectados 
    }
    
    return ruta_salida, datos_json