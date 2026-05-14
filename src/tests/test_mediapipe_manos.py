import pytest
from unittest.mock import patch, MagicMock

# Prevención de peticiones de red externas durante la fase de testing 
with patch('urllib.request.urlretrieve'), patch('os.makedirs'):
    from app.services.ai_factory.mediapipe_modelo.manos import procesar_manos

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

@patch('app.services.ai_factory.mediapipe_modelo.manos.cv2.imread')
@patch('app.services.ai_factory.mediapipe_modelo.manos.cv2.cvtColor')
@patch('app.services.ai_factory.mediapipe_modelo.manos.mp.Image')
@patch('app.services.ai_factory.mediapipe_modelo.manos.vision.HandLandmarker.create_from_options')
@patch('app.services.ai_factory.mediapipe_modelo.manos.cv2.imwrite')
def test_procesar_manos_fallo_escritura_silencioso_capturado(mock_imwrite, mock_detector, mock_mp_image, mock_cvt, mock_imread):
    """
    Auditoría de persistencia: Simula una denegación de escritura en disco (ej. permisos / espacio).
    Comprueba que el código evalúa el retorno de cv2.imwrite y propaga un IOError.
    """
    # Bypass de la detección visual
    mock_imread.return_value = MagicMock()
    mock_context = MagicMock()
    mock_context.__enter__.return_value.detect.return_value = MagicMock(handedness=[])
    mock_detector.return_value = mock_context

    # Inyección del fallo (OpenCV devuelve False en lugar de fallar)
    mock_imwrite.return_value = False 
    
    # Exigimos la propagación estructurada del error (IOError)
    with pytest.raises(IOError) as exc:
        procesar_manos("/tmp/input.jpg")
    
    assert "Imposible persistir el activo" in str(exc.value)