import pytest
from unittest.mock import patch
from app.services.ai_factory.yolo.launcher import YoloLauncher

# ------------------------------------------------------------------------------
# 1. PRUEBAS DE DESPACHO NOMINAL (RUTAS CRÍTICAS DE ÉXITO)
# ------------------------------------------------------------------------------

@patch('app.services.ai_factory.yolo.launcher.procesar_deteccion')
def test_ejecutar_modo_deteccion_exito(mock_deteccion):
    """Verifica que el identificador 'deteccion' enruta correctamente la ejecución."""
    mock_deteccion.return_value = ("ruta_deteccion.jpg", {"objetos": 2})
    launcher = YoloLauncher()
    
    ruta, meta = launcher.ejecutar_modo("deteccion", "/tmp/img.jpg", {"conf": 0.5})
    
    mock_deteccion.assert_called_once_with("/tmp/img.jpg", {"conf": 0.5}, "")
    assert ruta == "ruta_deteccion.jpg"
    assert meta["objetos"] == 2

@patch('app.services.ai_factory.yolo.launcher.procesar_recortes_personas')
def test_ejecutar_modo_recortes_exito(mock_recortes):
    """
    Verifica que el identificador 'recortes_personas' enruta la ejecución 
    y que el sistema es tolerante a espacios y mayúsculas en el identificador.
    """
    mock_recortes.return_value = (["ruta1.jpg", "ruta2.jpg"], {"recortes": 2})
    launcher = YoloLauncher()
    
    rutas, meta = launcher.ejecutar_modo(" RECORTES_PERSONAS ", "/tmp/img.jpg", prefijo="tfg")
    
    mock_recortes.assert_called_once_with("/tmp/img.jpg", {}, "tfg")
    assert len(rutas) == 2

# ------------------------------------------------------------------------------
# 2. PRUEBAS DE PROTECCIÓN E INTEGRIDAD DE PROTOCOLO
# ------------------------------------------------------------------------------

def test_ejecutar_modo_inexistente_falla_correctamente():
    """Valida la denegación de servicio controlada ante operaciones no registradas."""
    launcher = YoloLauncher()
    
    with pytest.raises(ValueError) as exc:
        launcher.ejecutar_modo("segmentacion_instancias", "/tmp/img.jpg")
    
    assert "no está implementado" in str(exc.value)

def test_ejecutar_modo_input_invalido_falla_correctamente():
    """Comprueba que el launcher rechaza modos nulos o no textuales antes de normalizarlos."""
    launcher = YoloLauncher()
    
    # 1. Auditoría contra inyección de valores nulos
    with pytest.raises(ValueError) as exc_none:
        launcher.ejecutar_modo(None, "/tmp/img.jpg")
    assert "obligatorio y debe ser una cadena de texto" in str(exc_none.value)

    # 2. Auditoría contra inyección de tipos numéricos
    with pytest.raises(ValueError) as exc_num:
        launcher.ejecutar_modo(404, "/tmp/img.jpg")
    assert "obligatorio y debe ser una cadena de texto" in str(exc_num.value)