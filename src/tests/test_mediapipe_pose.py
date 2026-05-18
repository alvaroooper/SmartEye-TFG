import pytest
from unittest.mock import patch, MagicMock

from app.services.ai_factory.mediapipe_modelo.pose import (
    procesar_pose,
    _asegurar_modelo_pose,
    _valor_float_opcional
)
def objeto_test(**atributos):
    """Crea un objeto simple con los atributos necesarios para simular salidas de MediaPipe."""
    obj = type("ObjetoTest", (), {})()

    for nombre, valor in atributos.items():
        setattr(obj, nombre, valor)

    return obj

# ==============================================================================
# 1. PRUEBAS DE PROTECCIÓN DE ENTRADA
# ==============================================================================

@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.imread')
def test_procesar_pose_configuracion_corrupta(mock_imread):
    """
    Exige la validación temprana de tipos en la configuración del modelo.
    Protege contra valores no numéricos en parámetros de inferencia.
    """
    config_maliciosa = {
        "model_complexity": "alto",
        "min_detection_confidence": "seguro"
    }

    with pytest.raises(ValueError) as exc:
        procesar_pose("/tmp/input.jpg", config=config_maliciosa)

    assert "deben ser numéricos" in str(exc.value).lower()
    mock_imread.assert_not_called()


@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.imread')
def test_procesar_pose_imagen_invalida(mock_imread):
    """
    Verifica que el servicio rechaza activos inexistentes o corruptos
    antes de cargar el modelo de MediaPipe.
    """
    mock_imread.return_value = None

    with pytest.raises(ValueError) as exc:
        procesar_pose("/ruta/fantasma.jpg")

    assert "No se pudo leer el activo" in str(exc.value)


# ==============================================================================
# 2. PRUEBA DE HARDENING DE ESCRITURA
# ==============================================================================

@patch('app.services.ai_factory.mediapipe_modelo.pose._asegurar_modelo_pose', return_value="/tmp/pose_landmarker_full.task")
@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.imread')
@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.cvtColor')
@patch('app.services.ai_factory.mediapipe_modelo.pose.mp.Image')
@patch('app.services.ai_factory.mediapipe_modelo.pose.vision.PoseLandmarker.create_from_options')
@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.imwrite')
def test_procesar_pose_fallo_escritura_silencioso(
    mock_imwrite,
    mock_detector,
    mock_mp_image,
    mock_cvt,
    mock_imread,
    mock_modelo
):
    """
    Simula una denegación de escritura en disco.
    Exige que el código evalúe el retorno de cv2.imwrite y propague un IOError.
    """
    mock_imread.return_value = MagicMock()
    mock_cvt.return_value = MagicMock()
    mock_mp_image.return_value = MagicMock()

    mock_context = MagicMock()
    mock_context.__enter__.return_value.detect.return_value = MagicMock(
        pose_landmarks=[]
    )
    mock_detector.return_value = mock_context

    mock_imwrite.return_value = False

    with pytest.raises(IOError) as exc:
        procesar_pose("/tmp/input.jpg")

    assert "Imposible persistir" in str(exc.value)


# ==============================================================================
# 3. PRUEBAS DE APROVISIONAMIENTO LOCAL DEL MODELO
# ==============================================================================

@patch('app.services.ai_factory.mediapipe_modelo.pose.urllib.request.urlretrieve')
@patch('app.services.ai_factory.mediapipe_modelo.pose.os.path.isfile', return_value=True)
def test_asegurar_modelo_pose_usa_modelo_local(mock_isfile, mock_urlretrieve):
    """
    Si el modelo ya existe en local, no debe realizar ninguna descarga.
    """
    ruta = _asegurar_modelo_pose()

    assert ruta.endswith("models/mp/pose_landmarker_full.task")
    mock_urlretrieve.assert_not_called()


@patch('app.services.ai_factory.mediapipe_modelo.pose.os.makedirs')
@patch('app.services.ai_factory.mediapipe_modelo.pose.os.path.isfile', side_effect=[False, True])
@patch('app.services.ai_factory.mediapipe_modelo.pose.os.path.getsize', return_value=1024)
@patch('app.services.ai_factory.mediapipe_modelo.pose.urllib.request.urlretrieve')
@patch('app.services.ai_factory.mediapipe_modelo.pose.os.replace')
def test_asegurar_modelo_pose_descarga_si_falta(
    mock_replace,
    mock_urlretrieve,
    mock_getsize,
    mock_isfile,
    mock_makedirs
):
    """
    Si el modelo no existe, debe descargarse una vez y quedar almacenado
    en la ruta local definitiva.
    """
    ruta = _asegurar_modelo_pose()

    assert ruta.endswith("models/mp/pose_landmarker_full.task")
    mock_urlretrieve.assert_called_once()
    mock_replace.assert_called_once()

# ==============================================================================
# 4. PRUEBAS DE FLUJO NOMINAL CON MEDIAPIPE TASKS API
# ==============================================================================

@patch('app.services.ai_factory.mediapipe_modelo.pose._asegurar_modelo_pose', return_value="/tmp/pose_landmarker_full.task")
@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.imread')
@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.cvtColor')
@patch('app.services.ai_factory.mediapipe_modelo.pose.mp.Image')
@patch('app.services.ai_factory.mediapipe_modelo.pose.vision.PoseLandmarker.create_from_options')
@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.imwrite')
def test_procesar_pose_exito_sin_detecciones(
    mock_imwrite,
    mock_detector,
    mock_mp_image,
    mock_cvt,
    mock_imread,
    mock_modelo
):
    """
    Valida el flujo correcto cuando la imagen se procesa, pero no se detecta pose.
    """
    mock_imread.return_value = MagicMock()
    mock_cvt.return_value = MagicMock()
    mock_mp_image.return_value = MagicMock()

    mock_context = MagicMock()
    mock_context.__enter__.return_value.detect.return_value = MagicMock(
        pose_landmarks=[]
    )
    mock_detector.return_value = mock_context
    mock_imwrite.return_value = True

    ruta, datos = procesar_pose(
        "/tmp/input.jpg",
        config={
            "num_poses": 1,
            "min_detection_confidence": 0.6,
            "min_pose_presence_confidence": 0.5,
            "min_tracking_confidence": 0.5
        },
        prefijo="test"
    )

    assert ruta == "/tmp/test_mp_pose_input.jpg"
    assert datos["pose_detectada"] is False
    assert datos["total_puntos"] == 0
    assert datos["detalles"] == []

    mock_detector.assert_called_once()
    mock_imwrite.assert_called_once()


@patch('app.services.ai_factory.mediapipe_modelo.pose._asegurar_modelo_pose', return_value="/tmp/pose_landmarker_full.task")
@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.imread')
@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.cvtColor')
@patch('app.services.ai_factory.mediapipe_modelo.pose.mp.Image')
@patch('app.services.ai_factory.mediapipe_modelo.pose.vision.PoseLandmarker.create_from_options')
@patch('app.services.ai_factory.mediapipe_modelo.pose.mp_drawing.draw_landmarks')
@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.imwrite')
def test_procesar_pose_exito_con_detecciones(
    mock_imwrite,
    mock_draw_landmarks,
    mock_detector,
    mock_mp_image,
    mock_cvt,
    mock_imread,
    mock_modelo
):
    """
    Verifica la serialización de landmarks cuando MediaPipe detecta una pose.
    """
    mock_imread.return_value = MagicMock()
    mock_cvt.return_value = MagicMock()
    mock_mp_image.return_value = MagicMock()

    landmark = objeto_test(
        x=0.123456,
        y=0.234567,
        z=-0.345678,
        visibility=0.98765,
        presence=0.87654
    )

    resultado = MagicMock(
        pose_landmarks=[[landmark]]
    )

    mock_context = MagicMock()
    mock_context.__enter__.return_value.detect.return_value = resultado
    mock_detector.return_value = mock_context
    mock_imwrite.return_value = True

    ruta, datos = procesar_pose("/tmp/input.jpg", prefijo="pose")

    assert ruta == "/tmp/pose_mp_pose_input.jpg"
    assert datos["pose_detectada"] is True
    assert datos["total_puntos"] == 1
    assert datos["detalles"][0]["id"] == 0
    assert datos["detalles"][0]["parte_cuerpo"] == "NOSE"
    assert datos["detalles"][0]["coordenadas"]["x"] == 0.1235
    assert datos["detalles"][0]["coordenadas"]["y"] == 0.2346
    assert datos["detalles"][0]["coordenadas"]["z"] == -0.3457
    assert datos["detalles"][0]["visibilidad"] == 0.9877
    assert datos["detalles"][0]["presencia"] == 0.8765

    mock_draw_landmarks.assert_called_once()
    mock_imwrite.assert_called_once()


@patch('app.services.ai_factory.mediapipe_modelo.pose._asegurar_modelo_pose', return_value="/tmp/pose_landmarker_full.task")
@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.imread')
@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.cvtColor')
@patch('app.services.ai_factory.mediapipe_modelo.pose.mp.Image')
@patch('app.services.ai_factory.mediapipe_modelo.pose.vision.PoseLandmarker.create_from_options')
@patch('app.services.ai_factory.mediapipe_modelo.pose.mp_drawing.draw_landmarks')
@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.imwrite')
def test_procesar_pose_landmark_fuera_de_catalogo_y_campos_opcionales(
    mock_imwrite,
    mock_draw_landmarks,
    mock_detector,
    mock_mp_image,
    mock_cvt,
    mock_imread,
    mock_modelo
):
    """
    Cubre landmarks cuyo índice no existe en el enum de MediaPipe y campos opcionales ausentes.
    """
    mock_imread.return_value = MagicMock()
    mock_cvt.return_value = MagicMock()
    mock_mp_image.return_value = MagicMock()

    landmarks = [
        objeto_test(x=0.1, y=0.2, z=0.3, visibility=0.9, presence=0.8)
        for _ in range(34)
    ]

    delattr(landmarks[33], "presence")

    resultado = MagicMock(
        pose_landmarks=[landmarks]
    )

    mock_context = MagicMock()
    mock_context.__enter__.return_value.detect.return_value = resultado
    mock_detector.return_value = mock_context
    mock_imwrite.return_value = True

    ruta, datos = procesar_pose("/tmp/input.jpg")

    assert ruta == "/tmp/mp_pose_input.jpg"
    assert datos["pose_detectada"] is True
    assert datos["total_puntos"] == 34
    assert datos["detalles"][33]["parte_cuerpo"] == "LANDMARK_33"
    assert datos["detalles"][33]["presencia"] is None

    mock_draw_landmarks.assert_called_once()
    mock_imwrite.assert_called_once()


# ==============================================================================
# 5. PRUEBAS DE VALIDACIÓN DE CONFIGURACIÓN
# ==============================================================================

def test_procesar_pose_rechaza_num_poses_no_positivo():
    """
    num_poses debe ser positivo para evitar configuraciones inválidas del detector.
    """
    with pytest.raises(ValueError) as exc:
        procesar_pose("/tmp/input.jpg", config={"num_poses": 0})

    assert "num_poses" in str(exc.value)


def test_valor_float_opcional_normaliza_ausentes_e_invalidos():
    """
    Verifica el helper que normaliza coordenadas y métricas opcionales de landmarks.
    """
    landmark_valido = objeto_test(x=0.123456)
    landmark_sin_valor = objeto_test()
    landmark_invalido = objeto_test(x="no-numerico")

    assert _valor_float_opcional(landmark_valido, "x") == 0.1235
    assert _valor_float_opcional(landmark_sin_valor, "x") is None
    assert _valor_float_opcional(landmark_invalido, "x") is None


# ==============================================================================
# 6. PRUEBA DE FALLO EN APROVISIONAMIENTO DEL MODELO
# ==============================================================================

@patch('app.services.ai_factory.mediapipe_modelo.pose.os.remove')
@patch('app.services.ai_factory.mediapipe_modelo.pose.os.path.exists', return_value=True)
@patch('app.services.ai_factory.mediapipe_modelo.pose.urllib.request.urlretrieve')
@patch('app.services.ai_factory.mediapipe_modelo.pose.os.path.isfile', side_effect=[False, False])
@patch('app.services.ai_factory.mediapipe_modelo.pose.os.makedirs')
def test_asegurar_modelo_pose_limpia_temporal_si_descarga_falla(
    _mock_makedirs,
    _mock_isfile,
    mock_urlretrieve,
    _mock_exists,
    mock_remove
):
    """
    Si la descarga no genera un modelo válido, debe limpiarse el temporal corrupto.
    """
    with pytest.raises(RuntimeError) as exc:
        _asegurar_modelo_pose()

    assert "No se pudo descargar el modelo" in str(exc.value)
    mock_urlretrieve.assert_called_once()
    mock_remove.assert_called_once()