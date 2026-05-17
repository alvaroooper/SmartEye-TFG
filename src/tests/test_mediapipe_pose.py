import pytest
from unittest.mock import patch, MagicMock

from app.services.ai_factory.mediapipe_modelo.pose import (
    procesar_pose,
    _asegurar_modelo_pose
)


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