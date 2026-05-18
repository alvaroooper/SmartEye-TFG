import pytest
from unittest.mock import patch, MagicMock

from app.services.ai_factory.mediapipe_modelo.manos import (
    procesar_manos,
    _asegurar_modelo_manos
)

def objeto_test(**atributos):
    """Crea un objeto simple con los atributos necesarios para simular salidas de MediaPipe."""
    obj = type("ObjetoTest", (), {})()

    for nombre, valor in atributos.items():
        setattr(obj, nombre, valor)

    return obj
# ==============================================================================
# 1. PRUEBAS DE RESILIENCIA DE INPUTS 
# ==============================================================================

@patch('app.services.ai_factory.mediapipe_modelo.manos.cv2.imread')
def test_procesar_manos_imagen_invalida(mock_imread):
    """Verifica que el servicio rechaza activos inexistentes o corruptos de forma controlada."""
    mock_imread.return_value = None
    
    with pytest.raises(ValueError) as exc:
        procesar_manos("/ruta/inexistente.jpg")
    
    assert "Fallo en la lectura del activo" in str(exc.value)

@patch('app.services.ai_factory.mediapipe_modelo.manos.cv2.imread')
def test_procesar_manos_configuracion_corrupta(mock_imread):
    """
    Exige la validación de tipos en la configuración del modelo.
    Protege contra inyecciones de strings en campos que requieren parámetros numéricos (Float/Int).
    """
    mock_imread.return_value = MagicMock()
    config_maliciosa = {"min_detection_confidence": "texto_invalido"}
    
    with pytest.raises(ValueError) as exc:
        procesar_manos("/tmp/input.jpg", config=config_maliciosa)
        
    assert "deben ser numéricos" in str(exc.value).lower()

# ==============================================================================
# 2. PRUEBA DE HARDENING DE LIBRERÍAS DE TERCEROS 
# ==============================================================================
@patch('app.services.ai_factory.mediapipe_modelo.manos._asegurar_modelo_manos', return_value="/tmp/hand_landmarker.task")
@patch('app.services.ai_factory.mediapipe_modelo.manos.cv2.imread')
@patch('app.services.ai_factory.mediapipe_modelo.manos.cv2.cvtColor')
@patch('app.services.ai_factory.mediapipe_modelo.manos.mp.Image')
@patch('app.services.ai_factory.mediapipe_modelo.manos.vision.HandLandmarker.create_from_options')
@patch('app.services.ai_factory.mediapipe_modelo.manos.cv2.imwrite')
def test_procesar_manos_fallo_escritura_silencioso_capturado(mock_imwrite, mock_detector, _mock_mp_image, _mock_cvt, mock_imread, _mock_modelo):
    """
    Auditoría de persistencia: Simula una denegación de escritura en disco (ej. permisos / espacio).
    Comprueba que el código evalúa el retorno de cv2.imwrite y propaga un IOError.
    """
    # Bypass de la detección visual
    mock_imread.return_value = MagicMock()
    mock_context = MagicMock()
    mock_context.__enter__.return_value.detect.return_value = MagicMock(handedness=[])
    mock_detector.return_value = mock_context

    mock_imwrite.return_value = False 
    
    # Exigimos la propagación estructurada del error (IOError)
    with pytest.raises(IOError) as exc:
        procesar_manos("/tmp/input.jpg")
    
    assert "Imposible persistir el activo" in str(exc.value)

# ==============================================================================
# 3. PRUEBAS DE FLUJO NOMINAL
# ==============================================================================

@patch('app.services.ai_factory.mediapipe_modelo.manos._asegurar_modelo_manos', return_value="/tmp/hand_landmarker.task")
@patch('app.services.ai_factory.mediapipe_modelo.manos.cv2.imread')
@patch('app.services.ai_factory.mediapipe_modelo.manos.cv2.cvtColor')
@patch('app.services.ai_factory.mediapipe_modelo.manos.mp.Image')
@patch('app.services.ai_factory.mediapipe_modelo.manos.vision.HandLandmarker.create_from_options')
@patch('app.services.ai_factory.mediapipe_modelo.manos.cv2.imwrite')
def test_procesar_manos_exito_sin_detecciones(
    mock_imwrite,
    mock_detector,
    mock_mp_image,
    mock_cvt,
    mock_imread,
    _mock_modelo
):
    """
    Valida el flujo correcto cuando la imagen se procesa, pero no se detectan manos.
    """
    mock_imread.return_value = MagicMock()
    mock_cvt.return_value = MagicMock()
    mock_mp_image.return_value = MagicMock()

    mock_context = MagicMock()
    mock_context.__enter__.return_value.detect.return_value = MagicMock(
        handedness=[],
        hand_landmarks=[]
    )
    mock_detector.return_value = mock_context
    mock_imwrite.return_value = True

    ruta, datos = procesar_manos(
        "/tmp/input.jpg",
        config={
            "max_num_hands": 2,
            "min_detection_confidence": 0.6
        },
        prefijo="test"
    )

    assert ruta == "/tmp/test_mp_input.jpg"
    assert datos["manos_detectadas"] == 0
    assert datos["detalles"] == []

    mock_detector.assert_called_once()
    mock_imwrite.assert_called_once()

@patch('app.services.ai_factory.mediapipe_modelo.manos._asegurar_modelo_manos', return_value="/tmp/hand_landmarker.task")
@patch('app.services.ai_factory.mediapipe_modelo.manos.cv2.imread')
@patch('app.services.ai_factory.mediapipe_modelo.manos.cv2.cvtColor')
@patch('app.services.ai_factory.mediapipe_modelo.manos.mp.Image')
@patch('app.services.ai_factory.mediapipe_modelo.manos.vision.HandLandmarker.create_from_options')
@patch('app.services.ai_factory.mediapipe_modelo.manos.mp.solutions.drawing_utils.draw_landmarks')
@patch('app.services.ai_factory.mediapipe_modelo.manos.cv2.imwrite')
def test_procesar_manos_exito_con_detecciones(
    mock_imwrite,
    mock_draw_landmarks,
    mock_detector,
    mock_mp_image,
    mock_cvt,
    mock_imread,
    _mock_modelo
):
    """
    Verifica la extracción de metadatos cuando MediaPipe detecta una mano.
    """
    mock_imread.return_value = MagicMock()
    mock_cvt.return_value = MagicMock()
    mock_mp_image.return_value = MagicMock()

    categoria = objeto_test(
        category_name="Left",
        score=0.98765
    )

    landmark = objeto_test(
        x=0.1,
        y=0.2,
        z=0.3
    )

    resultado = MagicMock(
        handedness=[[categoria]],
        hand_landmarks=[[landmark]]
    )

    mock_context = MagicMock()
    mock_context.__enter__.return_value.detect.return_value = resultado
    mock_detector.return_value = mock_context

    mock_imwrite.return_value = True

    ruta, datos = procesar_manos("/tmp/input.jpg", prefijo="mano")

    assert ruta == "/tmp/mano_mp_input.jpg"
    assert datos["manos_detectadas"] == 1
    assert datos["detalles"][0]["tipo"] == "Left"
    assert datos["detalles"][0]["confianza"] == 0.9877

    mock_draw_landmarks.assert_called_once()
    mock_imwrite.assert_called_once()


# ==============================================================================
# 4. PRUEBAS DE APROVISIONAMIENTO LOCAL DEL MODELO
# ==============================================================================

@patch('app.services.ai_factory.mediapipe_modelo.manos.urllib.request.urlretrieve')
@patch('app.services.ai_factory.mediapipe_modelo.manos.os.makedirs')
@patch('app.services.ai_factory.mediapipe_modelo.manos.os.path.isfile', return_value=True)
def test_asegurar_modelo_manos_usa_modelo_local(
    mock_isfile,
    mock_makedirs,
    mock_urlretrieve
):
    """
    Si el modelo ya existe en local, no debe realizar ninguna descarga.
    """
    ruta = _asegurar_modelo_manos()

    assert ruta.endswith("models/mp/hand_landmarker.task")
    mock_makedirs.assert_called_once()
    mock_urlretrieve.assert_not_called()


@patch('app.services.ai_factory.mediapipe_modelo.manos.os.replace')
@patch('app.services.ai_factory.mediapipe_modelo.manos.urllib.request.urlretrieve')
@patch('app.services.ai_factory.mediapipe_modelo.manos.os.path.getsize', return_value=1024)
@patch('app.services.ai_factory.mediapipe_modelo.manos.os.path.isfile', side_effect=[False, True])
@patch('app.services.ai_factory.mediapipe_modelo.manos.os.makedirs')
def test_asegurar_modelo_manos_descarga_si_falta(
    mock_makedirs,
    mock_isfile,
    mock_getsize,
    mock_urlretrieve,
    mock_replace
):
    """
    Si el modelo no existe, debe descargarse a un temporal y moverse a la ruta final.
    """
    ruta = _asegurar_modelo_manos()

    assert ruta.endswith("models/mp/hand_landmarker.task")
    mock_urlretrieve.assert_called_once()
    mock_getsize.assert_called_once()
    mock_replace.assert_called_once()


@patch('app.services.ai_factory.mediapipe_modelo.manos.os.remove')
@patch('app.services.ai_factory.mediapipe_modelo.manos.os.path.exists', return_value=True)
@patch('app.services.ai_factory.mediapipe_modelo.manos.urllib.request.urlretrieve')
@patch('app.services.ai_factory.mediapipe_modelo.manos.os.path.isfile', side_effect=[False, False])
@patch('app.services.ai_factory.mediapipe_modelo.manos.os.makedirs')
def test_asegurar_modelo_manos_limpia_temporal_si_descarga_falla(
    mock_makedirs,
    mock_isfile,
    mock_urlretrieve,
    mock_exists,
    mock_remove
):
    """
    Si la descarga no genera un modelo válido, debe eliminarse el temporal corrupto.
    """
    with pytest.raises(RuntimeError) as exc:
        _asegurar_modelo_manos()

    assert "No se pudo descargar el modelo" in str(exc.value)
    mock_urlretrieve.assert_called_once()
    mock_remove.assert_called_once()