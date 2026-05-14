import pytest
from unittest.mock import patch, MagicMock

# La importación se realiza a nivel de módulo para garantizar que las librerías 
# subyacentes (como OpenCV) se carguen correctamente antes de aplicar los mocks.
from app.services.pipeline_runner import PipelineRunner

# ------------------------------------------------------------------------------
# 1. PRUEBAS DE INTEGRIDAD Y VALIDACIÓN TEMPRANA (FAIL-FAST)
# ------------------------------------------------------------------------------

@patch("app.services.pipeline_runner.os.path.exists")
def test_pipeline_imagen_inexistente(mock_exists):
    """
    Verifica que el orquestador aborta la ejecución si el activo de origen 
    no se localiza en el sistema de archivos.
    """
    # Se simula la ausencia del archivo físico
    mock_exists.return_value = False
    
    with pytest.raises(ValueError) as exc:
        # Se incluye el cuarto argumento 'prefijo' para cumplir con la firma del método
        PipelineRunner.ejecutar_pipeline(1, "/tmp/archivo_inexistente.jpg", {}, "tfg_audit")
        
    assert "no existe o es inaccesible" in str(exc.value).lower()

@patch("app.services.pipeline_runner.PipelineEtapa")
@patch("app.services.pipeline_runner.os.path.exists")
def test_pipeline_sin_nodos_operativos(mock_exists, mock_etapa):
    """
    Audita el comportamiento del sistema ante una definición de pipeline vacía.
    Garantiza que no se inicie el procesamiento si no hay etapas configuradas.
    """
    mock_exists.return_value = True
    
    # Simulación de una consulta a la base de datos que no devuelve registros
    mock_query = MagicMock()
    mock_query.filter_by.return_value.order_by.return_value.all.return_value = []
    mock_etapa.query = mock_query
    
    with pytest.raises(ValueError) as exc:
        PipelineRunner.ejecutar_pipeline(99, "/tmp/imagen.jpg", {}, "tfg_audit")
        
    assert "carece de nodos operativos" in str(exc.value).lower()

# ------------------------------------------------------------------------------
# 2. PRUEBAS DE LÓGICA DE NEGOCIO Y CONTROL DE FLUJO
# ------------------------------------------------------------------------------

@patch("app.services.pipeline_runner.AIFactory")
@patch("app.services.pipeline_runner.PipelineEtapa")
@patch("app.services.pipeline_runner.os.path.exists")
def test_pipeline_early_stopping(mock_exists, mock_etapa, mock_factory):
    """
    Valida la regla de parada temprana (Early Stopping).
    Si un modelo de detección no genera resultados, el pipeline debe detenerse
    para evitar el desperdicio de recursos computacionales.
    """
    mock_exists.return_value = True
    
    # Mock de una etapa de detección válida
    etapa_falsa = MagicMock()
    etapa_falsa.nombre = "Deteccion Inicial"
    etapa_falsa.modelo.nombre = "yolo"
    etapa_falsa.modo.nombre_modo = "deteccion"
    
    mock_query = MagicMock()
    mock_query.filter_by.return_value.order_by.return_value.all.return_value = [etapa_falsa]
    mock_etapa.query = mock_query

    # Simulación de un motor de IA que no encuentra objetos en la imagen
    mock_launcher = MagicMock()
    mock_launcher.ejecutar_modo.return_value = ([], {"objetos": 0})
    mock_factory.get_launcher.return_value = mock_launcher

    with pytest.raises(ValueError) as exc:
        PipelineRunner.ejecutar_pipeline(1, "/tmp/imagen.jpg", {}, "tfg_audit")
        
    assert "análisis interrumpido" in str(exc.value).lower()

@patch("app.services.pipeline_runner.AIFactory")
@patch("app.services.pipeline_runner.PipelineEtapa")
@patch("app.services.pipeline_runner.os.path.exists")
def test_pipeline_ejecucion_completa_ramificada(mock_exists, mock_etapa, mock_factory):
    """Comprueba que una imagen válida ejecuta el pipeline y devuelve tokens de salida."""

    mock_exists.return_value = True
    
    # Simulación de dos etapas encadenadas: Detección -> Análisis
    etapa1 = MagicMock(orden=1, nombre="Segmentacion")
    etapa1.modelo.nombre = "yolo"
    etapa1.modo.nombre_modo = "recortes"
    
    etapa2 = MagicMock(orden=2, nombre="Analisis Postura")
    etapa2.modelo.nombre = "mediapipe"
    etapa2.modo.nombre_modo = "pose"
    
    mock_query = MagicMock()
    mock_query.filter_by.return_value.order_by.return_value.all.return_value = [etapa1, etapa2]
    mock_etapa.query = mock_query

    # Mock del comportamiento de los motores de IA
    mock_launcher = MagicMock()
    
    def mock_ejecutar_modo(modo, ruta, config, prefijo):
        if modo == "recortes":
            # Genera 2 recortes a partir de 1 imagen original
            return (["/tmp/obj_1.jpg", "/tmp/obj_2.jpg"], {"sujetos": 2})
        else:
            # Procesa cada recorte individualmente
            return (f"{ruta}_analizado.jpg", {"status": "ok"})
            
    mock_launcher.ejecutar_modo.side_effect = mock_ejecutar_modo
    mock_factory.get_launcher.return_value = mock_launcher

    # Ejecución del flujo de trabajo completo
    rutas_finales, telemetria = PipelineRunner.ejecutar_pipeline(1, "/tmp/inicial.jpg", {}, "tfg_audit")

    # Verificación de la ramificación y persistencia
    assert len(rutas_finales) == 2
    assert "/tmp/obj_1.jpg_analizado.jpg" in rutas_finales
    assert "/tmp/obj_2.jpg_analizado.jpg" in rutas_finales
    
    # Verificación de la estructura de la telemetría (logs de auditoría)
    assert len(telemetria) == 2
    assert telemetria[0]["ia"] == "yolo"
    assert telemetria[1]["ia"] == "mediapipe"
    assert len(telemetria[1]["datos"]) == 2  # Se analizaron 2 imágenes en la etapa 2