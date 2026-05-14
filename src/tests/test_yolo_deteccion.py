import pytest
import os
from unittest.mock import patch, MagicMock

# ------------------------------------------------------------------------------
# 1. PRUEBAS DE VALIDACIÓN DE ENTRADA 
# ------------------------------------------------------------------------------

def test_procesar_deteccion_configuracion_corrupta():
    """
    Verifica que la lógica de validación de tipos rechaza parámetros no numéricos.
    Garantiza la integridad de los hiperparámetros antes de la ejecución del motor.
    """
    from app.services.ai_factory.yolo.deteccion import procesar_deteccion
    
    config_invalida = {
        "conf": "umbral_invalido", 
        "iou": "error_string",
        "imgsz": "no_int"
    }
    
    # Se simula la existencia del archivo de entrada para validar únicamente el parseo de config.
    with patch('os.path.exists', return_value=True):
        with pytest.raises(ValueError) as exc:
            procesar_deteccion("/tmp/input.jpg", config=config_invalida)
            
        assert "deben ser numéricos" in str(exc.value).lower()

def test_procesar_deteccion_imagen_inexistente():
    """
    Valida la respuesta del sistema ante la ausencia física del activo de entrada.
    Asegura que el servicio no inicie la inferencia si el archivo original no existe.
    """
    from app.services.ai_factory.yolo.deteccion import procesar_deteccion
    
    with patch('os.path.exists', return_value=False):
        with pytest.raises(ValueError) as exc:
            procesar_deteccion("/ruta/inexistente.jpg")
        
        assert "No se localizó el archivo" in str(exc.value)

# ------------------------------------------------------------------------------
# 2. PRUEBAS DE AUDITORÍA DE PERSISTENCIA 
# ------------------------------------------------------------------------------

@patch('app.services.ai_factory.yolo.deteccion._MODELO_YOLO_INSTANCE')
def test_procesar_deteccion_fallo_escritura_auditado(mock_yolo_instance):
    """
    Audita la capacidad del sistema para detectar fallos en la persistencia de salida.
    Simula una denegación de escritura y verifica la propagación de excepciones de I/O.
    """
    from app.services.ai_factory.yolo.deteccion import procesar_deteccion

    # Preparación de mocks para el objeto de resultados de la librería Ultralytics.
    mock_resultado = MagicMock()
    mock_resultado.boxes = [] 
    mock_yolo_instance.return_value = [mock_resultado]

    # Lógica de simulación selectiva para distinguir entre activo de entrada y salida.
    def side_effect_exists(path):
        # El archivo de salida se identifica por el prefijo de detección en la ruta.
        if "deteccion_" in path:
            return False 
        return True

    with patch('os.path.exists', side_effect=side_effect_exists):
        with pytest.raises(IOError) as exc:
            procesar_deteccion("/tmp/input.jpg")
            
        assert "Imposible persistir" in str(exc.value)
        # Se confirma que se intentó invocar el método de persistencia del motor.
        mock_resultado.save.assert_called_once()