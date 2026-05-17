import os
import cv2
import urllib.request
from typing import Tuple, Dict, Any
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ==============================================================================
# GESTOR DE APROVISIONAMIENTO Y CARGA DEL MODELO 
# ==============================================================================

# 1. Definición de rutas absolutas del sistema de archivos
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
MODEL_DIR = os.path.join(BASE_DIR, 'models', 'mp')
MODEL_PATH = os.path.join(MODEL_DIR, 'hand_landmarker.task')

# URL oficial del repositorio de Google para el modelo de detección palmar
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"

# 2. Rutina de Autodescarga
def _asegurar_modelo_manos() -> str:
    """
    Garantiza que el modelo de manos esté disponible en local.

    Si el archivo no existe en models/mp, se descarga la primera vez.
    En las siguientes ejecuciones se reutiliza el archivo local.
    """
    os.makedirs(MODEL_DIR, exist_ok=True)

    if os.path.isfile(MODEL_PATH):
        return MODEL_PATH

    print(f"--- [INFO] Descargando pesos de MediaPipe Manos en: {MODEL_PATH} ---")

    ruta_temporal = MODEL_PATH + ".tmp"

    try:
        urllib.request.urlretrieve(MODEL_URL, ruta_temporal)

        if not os.path.isfile(ruta_temporal) or os.path.getsize(ruta_temporal) == 0:
            raise RuntimeError("El modelo descargado está vacío o no se ha creado correctamente.")

        os.replace(ruta_temporal, MODEL_PATH)

    except Exception as exc:
        if os.path.exists(ruta_temporal):
            os.remove(ruta_temporal)

        raise RuntimeError(
            "No se pudo descargar el modelo hand_landmarker.task. "
            "Comprueba la conexión a Internet o coloca manualmente el archivo "
            f"en la ruta: {MODEL_PATH}"
        ) from exc

    return MODEL_PATH
# 3. Inicialización estática del motor local (Tasks API)
base_options = python.BaseOptions(model_asset_path=MODEL_PATH)


def procesar_manos(imagen_path: str, config: Dict[str, Any] = None, prefijo: str = "") -> Tuple[str, Dict[str, Any]]:
    """
    Detección de landmarks palmares utilizando MediaPipe Tasks API en modo local.
    """
    if config is None: 
        config = {}

    # ==========================================================================
    # 1. BASTIONADO: Sanitización temprana 
    # Validamos los inputs antes de realizar operaciones costosas en memoria.
    # ==========================================================================
    try:
        max_hands = int(config.get("max_num_hands", 2))
        min_conf = float(config.get("min_detection_confidence", 0.5))
    except (ValueError, TypeError):
        raise ValueError("Excepción de tipo: Los hiperparámetros de MediaPipe deben ser numéricos.")

    # ==========================================================================
    # 2. LECTURA Y PREPROCESAMIENTO DE IMAGEN
    # ==========================================================================
    imagen = cv2.imread(imagen_path)
    if imagen is None:
        raise ValueError(f"Excepción de I/O: Fallo en la lectura del activo de entrada: {imagen_path}")

    # Transformación del espacio de color requerido por MediaPipe Tasks API
    imagen_rgb = cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=imagen_rgb)
    
    datos_json = {"manos_detectadas": 0, "detalles": []}
    
    # ==========================================================================
    # 3. EJECUCIÓN DEL MOTOR DE INFERENCIA
    # ==========================================================================
    modelo_path = _asegurar_modelo_manos()
    base_options = python.BaseOptions(model_asset_path=modelo_path)

    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        num_hands=max_hands,
        min_hand_detection_confidence=min_conf
    )
    
    # Ejecución aislada de la inferencia (Context Manager)
    with vision.HandLandmarker.create_from_options(options) as detector:
        resultados = detector.detect(mp_image)
        
        # Extracción y estructuración de metadatos (Handedness & Landmarks)
        if resultados.handedness:
            datos_json["manos_detectadas"] = len(resultados.handedness)
            
            for idx, hand in enumerate(resultados.handedness):
                categoria = hand[0]
                datos_json["detalles"].append({
                    "tipo": categoria.category_name, # Left / Right
                    "confianza": round(categoria.score, 4)
                })
            
            # Post-procesamiento: Renderizado topológico sobre el activo original
            from mediapipe.framework.formats import landmark_pb2
            for hand_landmarks in resultados.hand_landmarks:
                hand_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
                hand_landmarks_proto.landmark.extend([
                    landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z) 
                    for landmark in hand_landmarks
                ])
                mp.solutions.drawing_utils.draw_landmarks(
                    imagen,
                    hand_landmarks_proto,
                    mp.solutions.hands.HAND_CONNECTIONS,
                    mp.solutions.drawing_utils.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                    mp.solutions.drawing_utils.DrawingSpec(color=(0, 0, 255), thickness=2)
                )

    # ==========================================================================
    # 4. PERSISTENCIA SEGURA Y PREVENCIÓN DE FALLO SILENCIOSO
    # ==========================================================================
    directorio = os.path.dirname(imagen_path)
    nombre_archivo = os.path.basename(imagen_path)
    str_prefijo = f"{prefijo}_" if prefijo else ""
    ruta_salida = os.path.join(directorio, f"{str_prefijo}mp_{nombre_archivo}")
    
    # cv2.imwrite devuelve un booleano. Su fallo no detiene la ejecución por defecto.
    exito_escritura = cv2.imwrite(ruta_salida, imagen)
    if not exito_escritura:
        raise IOError(f"Fallo crítico de sistema: Imposible persistir el activo en disco. Verifique permisos o espacio en: {ruta_salida}")
    
    return ruta_salida, datos_json