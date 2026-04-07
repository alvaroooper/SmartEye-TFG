def procesar_manos(imagen_path):
    print(f"[MediaPipe] Simulando detección de manos en: {imagen_path}")
    
    imagen_resultado = f"mp_manos_{imagen_path.split('/')[-1]}"
    datos_json = {"manos_detectadas": 2, "landmarks": True}
    
    return imagen_resultado, datos_json