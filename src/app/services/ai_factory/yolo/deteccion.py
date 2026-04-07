def procesar_deteccion(imagen_path):
    # En el futuro, aquí se hará la referencia real
    print(f"[YOLO] Simulando detección de objetos en: {imagen_path}")
    
    imagen_resultado = f"yolo_det_{imagen_path.split('/')[-1]}"
    datos_json = {"objetos": ["persona", "coche"], "confianza_media": 0.95}
    
    return imagen_resultado, datos_json