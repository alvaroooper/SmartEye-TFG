import pytest
import numpy as np
from unittest.mock import patch, MagicMock

# ------------------------------------------------------------------------------
# 1. PRUEBAS DE EXCEPCIONES (CASOS DE ERROR CONTROLADO)
# ------------------------------------------------------------------------------

@patch('app.services.ai_factory.yolo.recortes.cv2.imread')
def test_configuracion_invalida(mock_imread):
    """Verifica que el código lanza ValueError si los parámetros no son numéricos."""
    from app.services.ai_factory.yolo.recortes import procesar_recortes_personas
    
    # Le pasamos un string en lugar de un número
    config_erronea = {
        "conf": "texto_invalido",
        "iou": "texto_invalido",
        "imgsz": "texto_invalido",
        "scale_factor": "texto_invalido"
    }   
    
    with pytest.raises(ValueError) as exc:
        procesar_recortes_personas("/tmp/input.jpg", config=config_erronea)
        
    assert "deben ser numéricos" in str(exc.value).lower()
    # Verificamos que cv2.imread ni siquiera llegó a ejecutarse
    mock_imread.assert_not_called()

@patch('app.services.ai_factory.yolo.recortes.cv2.imread')
def test_imagen_inexistente(mock_imread):
    """Verifica que lanza ValueError si OpenCV no puede leer la imagen."""
    from app.services.ai_factory.yolo.recortes import procesar_recortes_personas
    
    # Simulamos que la imagen no existe
    mock_imread.return_value = None
    
    with pytest.raises(ValueError) as exc:
        procesar_recortes_personas("/tmp/fantasma.jpg")
        
    assert "imposible leer el activo" in str(exc.value).lower()

# ------------------------------------------------------------------------------
# 2. PRUEBA DE FLUJO COMPLETO (CASO DE ÉXITO)
# ------------------------------------------------------------------------------

@patch('app.services.ai_factory.yolo.recortes._MODELO_YOLO_INSTANCE')
@patch('app.services.ai_factory.yolo.recortes.cv2.imread')
@patch('app.services.ai_factory.yolo.recortes.cv2.resize')
@patch('app.services.ai_factory.yolo.recortes.cv2.imwrite')
def test_procesar_recortes_exito(mock_imwrite, mock_resize, mock_imread, mock_yolo):
    """
    Simula una detección exitosa de una persona y verifica que se generan
    las rutas y los metadatos correctamente sin usar el modelo real de IA.
    """
    from app.services.ai_factory.yolo.recortes import procesar_recortes_personas
    
    # 1. Simulamos imágenes con Numpy (matrices de píxeles)
    mock_imread.return_value = np.zeros((500, 500, 3), dtype=np.uint8)
    mock_resize.return_value = np.zeros((120, 120, 3), dtype=np.uint8)
    
    # 2. Simulamos la estructura de la Caja (Bounding Box) de YOLO
    mock_caja = MagicMock()
    
    # Simulamos el comportamiento de caja.xyxy[0].tolist()
    mock_xyxy = MagicMock()
    mock_xyxy.tolist.return_value = [10, 10, 50, 50]
    mock_caja.xyxy = [mock_xyxy]
    
    # Simulamos el comportamiento de caja.conf[0].item()
    mock_conf = MagicMock()
    mock_conf.item.return_value = 0.95
    mock_caja.conf = [mock_conf]
    
    # 3. Metemos la caja simulada dentro de los resultados
    mock_resultado = MagicMock()
    mock_resultado.boxes = [mock_caja]
    mock_yolo.return_value = [mock_resultado]
    
    # 4. Simulamos que OpenCV guarda la imagen sin problemas
    mock_imwrite.return_value = True
    
    # --- EJECUCIÓN ---
    rutas, datos_json = procesar_recortes_personas(
        imagen_path="/tmp/foto.jpg", 
        config={"conf": 0.5,"iou": 0.45,"imgsz": 640, "scale_factor": 2.0}, 
        prefijo="test"
    )
    
    # --- VERIFICACIÓN ---
    # Comprobamos que se generó una ruta de recorte
    assert len(rutas) == 1
    assert "recorte_0_foto.jpg" in rutas[0]
    
    # Comprobamos que el JSON de auditoría tiene los datos correctos
    assert datos_json["sujetos_localizados"] == 1
    assert datos_json["detalles"][0]["confianza"] == 0.95
    assert datos_json["detalles"][0]["resolucion_procesada"] == "80x80" # (50-10)*2.0
    
    # Verificamos que se llamó a guardar la imagen
    mock_imwrite.assert_called_once()