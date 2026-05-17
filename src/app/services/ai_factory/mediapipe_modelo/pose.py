import os
import cv2
import urllib.request
from typing import Tuple, Dict, Any

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.framework.formats import landmark_pb2


# ==============================================================================
# GESTOR DE APROVISIONAMIENTO Y CARGA DEL MODELO
# ==============================================================================

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
MODEL_DIR = os.path.join(BASE_DIR, "models", "mp")
MODEL_PATH = os.path.join(MODEL_DIR, "pose_landmarker_full.task")

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_full/float16/latest/"
    "pose_landmarker_full.task"
)

# Se usan estas utilidades clásicas de MediaPipe solo para nombres anatómicos
# y renderizado de conexiones sobre la imagen.
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils


def _asegurar_modelo_pose() -> str:
    """
    Garantiza que el modelo de pose esté disponible en local.

    Si el archivo pose_landmarker_full.task no existe en models/mp,
    se descarga la primera vez. En las siguientes ejecuciones se reutiliza
    el archivo local, evitando nuevas peticiones externas.
    """
    os.makedirs(MODEL_DIR, exist_ok=True)

    if os.path.isfile(MODEL_PATH):
        return MODEL_PATH

    print(f"--- [INFO] Descargando pesos de MediaPipe Pose en: {MODEL_PATH} ---")

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
            "No se pudo descargar el modelo pose_landmarker_full.task. "
            "Comprueba la conexión a Internet o coloca manualmente el archivo "
            f"en la ruta: {MODEL_PATH}"
        ) from exc

    return MODEL_PATH


def _valor_float_opcional(objeto: Any, atributo: str):
    """
    Extrae de forma segura un atributo numérico opcional de un landmark.
    Algunas versiones de MediaPipe pueden no devolver todos los campos.
    """
    valor = getattr(objeto, atributo, None)

    if valor is None:
        return None

    try:
        return round(float(valor), 4)
    except (ValueError, TypeError):
        return None


def procesar_pose(
    imagen_path: str,
    config: Dict[str, Any] = None,
    prefijo: str = ""
) -> Tuple[str, Dict[str, Any]]:
    """
    Estimación de pose humana utilizando MediaPipe Tasks API.

    El modelo se carga desde models/mp/pose_landmarker_full.task. Si no está
    disponible localmente, se descarga la primera vez y queda almacenado para
    las siguientes ejecuciones.
    """
    if config is None:
        config = {}

    # ==========================================================================
    # 1. VALIDACIÓN DE CONFIGURACIÓN
    # ==========================================================================
    try:
        # Se mantiene model_complexity por compatibilidad con configuraciones
        # anteriores, aunque en Tasks API la complejidad la determina el .task usado.
        if "model_complexity" in config:
            int(config.get("model_complexity"))

        num_poses = int(config.get("num_poses", 1))
        min_detection_conf = float(config.get("min_detection_confidence", 0.5))
        min_presence_conf = float(config.get("min_pose_presence_confidence", 0.5))
        min_tracking_conf = float(config.get("min_tracking_confidence", 0.5))

    except (ValueError, TypeError):
        raise ValueError("Excepción de tipo: Los hiperparámetros de Pose deben ser numéricos.")

    if num_poses <= 0:
        raise ValueError("Configuración inválida: num_poses debe ser mayor que cero.")

    # ==========================================================================
    # 2. LECTURA Y PREPROCESAMIENTO DE IMAGEN
    # ==========================================================================
    imagen = cv2.imread(imagen_path)

    if imagen is None:
        raise ValueError(f"No se pudo leer el activo de entrada para Pose: {imagen_path}")

    imagen_rgb = cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=imagen_rgb)

    datos_json = {
        "pose_detectada": False,
        "total_puntos": 0,
        "detalles": []
    }

    # ==========================================================================
    # 3. CARGA LOCAL DEL MODELO Y EJECUCIÓN
    # ==========================================================================
    modelo_path = _asegurar_modelo_pose()
    base_options = python.BaseOptions(model_asset_path=modelo_path)

    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.IMAGE,
        num_poses=num_poses,
        min_pose_detection_confidence=min_detection_conf,
        min_pose_presence_confidence=min_presence_conf,
        min_tracking_confidence=min_tracking_conf,
        output_segmentation_masks=False
    )

    with vision.PoseLandmarker.create_from_options(options) as detector:
        resultados = detector.detect(mp_image)

        if resultados.pose_landmarks:
            datos_json["pose_detectada"] = True

            # Se toma la primera pose como resultado principal para mantener
            # una salida sencilla y compatible con el flujo actual.
            pose_landmarks = resultados.pose_landmarks[0]
            datos_json["total_puntos"] = len(pose_landmarks)

            landmark_list = landmark_pb2.NormalizedLandmarkList()

            for idx, landmark in enumerate(pose_landmarks):
                try:
                    nombre_parte = mp_pose.PoseLandmark(idx).name
                except ValueError:
                    nombre_parte = f"LANDMARK_{idx}"

                datos_json["detalles"].append({
                    "id": idx,
                    "parte_cuerpo": nombre_parte,
                    "coordenadas": {
                        "x": _valor_float_opcional(landmark, "x"),
                        "y": _valor_float_opcional(landmark, "y"),
                        "z": _valor_float_opcional(landmark, "z")
                    },
                    "visibilidad": _valor_float_opcional(landmark, "visibility"),
                    "presencia": _valor_float_opcional(landmark, "presence")
                })

                landmark_list.landmark.append(
                    landmark_pb2.NormalizedLandmark(
                        x=float(landmark.x),
                        y=float(landmark.y),
                        z=float(landmark.z),
                        visibility=float(getattr(landmark, "visibility", 0.0) or 0.0)
                    )
                )

            # ==========================================================================
            # 4. RENDERIZADO DE LANDMARKS SOBRE LA IMAGEN ORIGINAL
            # ==========================================================================
            mp_drawing.draw_landmarks(
                imagen,
                landmark_list,
                mp_pose.POSE_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(255, 0, 0), thickness=2, circle_radius=2),
                mp_drawing.DrawingSpec(color=(0, 255, 255), thickness=2)
            )

    # ==========================================================================
    # 5. PERSISTENCIA SEGURA DEL ACTIVO RESULTANTE
    # ==========================================================================
    directorio = os.path.dirname(imagen_path)
    nombre_archivo = os.path.basename(imagen_path)
    str_prefijo = f"{prefijo}_" if prefijo else ""
    ruta_salida = os.path.join(directorio, f"{str_prefijo}mp_pose_{nombre_archivo}")

    exito_escritura = cv2.imwrite(ruta_salida, imagen)

    if not exito_escritura:
        raise IOError(
            f"Fallo crítico de sistema: Imposible persistir el activo esquelético en disco: {ruta_salida}"
        )

    return ruta_salida, datos_json