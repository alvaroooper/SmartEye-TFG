import pytest
from unittest.mock import patch
from app.services.ai_factory.mediapipe_modelo.launcher import MediaPipeLauncher

# ==============================================================================
# 1. PRUEBAS DE DESPACHO NOMINAL (SUCCESS CASES)
# ==============================================================================

@patch('app.services.ai_factory.mediapipe_modelo.launcher.procesar_manos')
def test_ejecutar_modo_manos_exito(mock_manos):
    """Verifica que el modo 'manos' invoca la estrategia correcta."""
    mock_manos.return_value = ("path/manos.jpg", {"landmarks": 21})
    launcher = MediaPipeLauncher()
    
    ruta, meta = launcher.ejecutar_modo("manos", "/tmp/input.jpg", config={"min_conf": 0.7})
    
    mock_manos.assert_called_once_with("/tmp/input.jpg", {"min_conf": 0.7}, "")
    assert ruta == "path/manos.jpg"
    assert meta["landmarks"] == 21

@patch('app.services.ai_factory.mediapipe_modelo.launcher.procesar_pose')
def test_ejecutar_modo_pose_exito(mock_pose):
    """Verifica que el modo 'pose' invoca la estrategia correcta y normaliza el nombre."""
    mock_pose.return_value = ("path/pose.jpg", {"puntos": 33})
    launcher = MediaPipeLauncher()
    
    ruta, meta = launcher.ejecutar_modo("POSE", "/tmp/input.jpg", prefijo="tfg_test")
    
    mock_pose.assert_called_once_with("/tmp/input.jpg", {}, "tfg_test")
    assert ruta == "path/pose.jpg"

# ==============================================================================
# 2. PRUEBAS DE PROTECCIÓN 
# ==============================================================================

def test_ejecutar_modo_inexistente_falla_correctamente():
    """Si el modo no existe, DEBE lanzar un ValueError controlado, no crashear."""
    launcher = MediaPipeLauncher()
    
    with pytest.raises(ValueError) as exc:
        launcher.ejecutar_modo("cara_deteccion", "/tmp/img.jpg")
    
    assert "no está implementado o registrado" in str(exc.value)

def test_ejecutar_modo_invalido_falla_correctamente():
    """Si el modo es nulo o numérico, DEBE lanzar un ValueError controlado, no crashear."""
    launcher = MediaPipeLauncher()
    
    with pytest.raises(ValueError) as exc:
        launcher.ejecutar_modo(None, "/tmp/img.jpg")
    
    assert "obligatorio y debe ser texto" in str(exc.value)
    
    with pytest.raises(ValueError):
        launcher.ejecutar_modo(123, "/tmp/img.jpg")