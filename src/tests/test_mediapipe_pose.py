import pytest
from unittest.mock import patch, MagicMock
from app.services.ai_factory.mediapipe_modelo.pose import procesar_pose

# ==============================================================================
# 1. PRUEBAS DE PROTECCIÓN DE ENTRADA 
# ==============================================================================

@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.imread')
def test_procesar_pose_configuracion_corrupta(mock_imread):
    """
    Exige la validación temprana de tipos en la configuración del modelo.
    Protege contra inyecciones que harían crashear el motor subyacente.
    """
    mock_imread.return_value = MagicMock()
    # Inyectamos strings donde el motor espera Int y Float
    config_maliciosa = {
        "model_complexity": "alto", 
        "min_detection_confidence": "seguro"
    }
    
    with pytest.raises(ValueError) as exc:
        procesar_pose("/tmp/input.jpg", config=config_maliciosa)
        
    assert "deben ser numéricos" in str(exc.value).lower()
    # Verificamos que cv2.imread NO llegó a ejecutarse
    mock_imread.assert_not_called()

@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.imread')
def test_procesar_pose_imagen_invalida(mock_imread):
    """Verifica que el servicio rechaza activos inexistentes controladamente."""
    # Simulamos que OpenCV no encuentra el archivo
    mock_imread.return_value = None
    
    with pytest.raises(ValueError) as exc:
        procesar_pose("/ruta/fantasma.jpg")
    
    assert "No se pudo leer el activo" in str(exc.value)

# ==============================================================================
# 2. PRUEBA DE HARDENING DE ESCRITURA 
# ==============================================================================

@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.imread')
@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.cvtColor')
@patch('app.services.ai_factory.mediapipe_modelo.pose.mp_pose.Pose')
@patch('app.services.ai_factory.mediapipe_modelo.pose.cv2.imwrite')
def test_procesar_pose_fallo_escritura_silencioso(mock_imwrite, mock_pose, mock_cvt, mock_imread):
    """
    Simula una denegación de escritura en disco (ej. permisos).
    Exige que el código evalúe el retorno de cv2.imwrite y propague un IOError.
    """
    # Bypass de la lectura y motor visual
    mock_imread.return_value = MagicMock()
    
    # Mock del Context Manager del motor Pose
    mock_context = MagicMock()
    # Simular que no encuentra landmarks para acelerar la prueba
    mock_context.__enter__.return_value.process.return_value = MagicMock(pose_landmarks=None)
    mock_pose.return_value = mock_context
    # Inyección del fallo (OpenCV devuelve False en lugar de lanzar una excepción)
    mock_imwrite.return_value = False 
    
    # Exigimos la propagación estructurada del IOError
    with pytest.raises(IOError) as exc:
        procesar_pose("/tmp/input.jpg")
    
    assert "Imposible persistir" in str(exc.value)