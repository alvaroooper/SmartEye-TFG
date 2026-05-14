import pytest
from unittest.mock import patch
from app.services.ai_factory import AIFactory

# ==============================================================================
# 1. PRUEBAS DE RESOLUCIÓN NOMINAL (SUCCESS CASES)
# ==============================================================================

def test_get_launcher_yolo_exito():
    """Verifica que el identificador 'yolo' instancia el controlador correcto."""
    with patch('app.services.ai_factory.YoloLauncher') as mock_yolo:
        launcher = AIFactory.get_launcher("yolo")
        assert launcher == mock_yolo.return_value
        mock_yolo.assert_called_once()

def test_get_launcher_mediapipe_exito():
    """Verifica que el identificador 'mediapipe' instancia el controlador correcto."""
    with patch('app.services.ai_factory.MediaPipeLauncher') as mock_mp:
        launcher = AIFactory.get_launcher("mediapipe")
        assert launcher == mock_mp.return_value
        mock_mp.assert_called_once()

def test_get_launcher_normalizacion():
    """Prueba que el Factory es inmune a mayúsculas y espacios en blanco."""
    with patch('app.services.ai_factory.YoloLauncher') as mock_yolo:
        launcher = AIFactory.get_launcher("  YOLO  ")
        assert launcher == mock_yolo.return_value

# ==============================================================================
# 2. PRUEBAS DE BASTIONADO (FAILURE PROTECTION)
# ==============================================================================

def test_get_launcher_modelo_no_registrado():
    """Verifica que un motor inexistente lanza la excepción ValueError adecuada."""
    with pytest.raises(ValueError) as exc:
        AIFactory.get_launcher("skynet_v1")
    
    assert "no está registrado" in str(exc.value)

def test_get_launcher_input_invalido():
    """
    Exige que el Factory valide el tipo de entrada de forma estricta.
    Si el código fuente NO tiene la guardia de seguridad, este test FALLARÁ.
    """
    # 1. Exigimos protección contra nulos (None)
    with pytest.raises(ValueError) as exc:
        AIFactory.get_launcher(None)
    
    assert "cadena válida" in str(exc.value)

    # 2. Exigimos protección contra tipos incorrectos (ej. un entero)
    with pytest.raises(ValueError) as exc_num:
        AIFactory.get_launcher(123)
        
    assert "cadena válida" in str(exc_num.value)