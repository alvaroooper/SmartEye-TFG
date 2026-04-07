import os
from ultralytics import YOLO # type: ignore

# Instanciamos el modelo fuera de la función para que no se recargue en cada petición.
# Al usar 'yolov8n.pt' (nano), Ultralytics descargará el archivo de pesos 
# automáticamente la primera vez que se ejecute.
modelo_yolo = YOLO('yolov8n.pt')

def procesar_deteccion(imagen_path):
    print(f"[YOLO] Ejecutando detección real en: {imagen_path}")
    
    # 1. Ejecutar inferencia
    resultados = modelo_yolo(imagen_path)
    
    # YOLO devuelve una lista (por si le pasas un lote de imágenes). 
    # Como le pasamos una sola, cogemos la primera.
    resultado = resultados[0]
    
    # 2. Generar ruta de salida
    directorio = os.path.dirname(imagen_path)
    nombre_archivo = os.path.basename(imagen_path)
    ruta_salida = os.path.join(directorio, f"yolo_{nombre_archivo}")
    
    # 3. Guardar la imagen con las predicciones dibujadas
    resultado.save(filename=ruta_salida)
    
    # 4. Extraer la información para el JSON
    objetos_detectados = []
    for caja in resultado.boxes:
        clase_id = int(caja.cls[0].item())
        nombre_clase = modelo_yolo.names[clase_id] # Pasa de ID (ej. 0) a Texto (ej. "person")
        confianza = round(caja.conf[0].item(), 2)
        
        objetos_detectados.append({
            "clase": nombre_clase,
            "confianza": confianza
        })
        
    datos_json = {
        "total_objetos": len(objetos_detectados),
        "detalles": objetos_detectados
    }
    
    return ruta_salida, datos_json