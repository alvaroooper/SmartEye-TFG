import pytest
from app.services.ai_factory.interface import IALauncherBase

# ==============================================================================
# 1. VALIDACIÓN DE ABSTRACCIÓN
# ==============================================================================

def test_interface_no_instanciable():
    """
    Verifica que la interfaz cumple con el protocolo ABC y no puede ser 
    instanciada directamente por el PipelineRunner.
    """
    with pytest.raises(TypeError) as exc:
        IALauncherBase()
    
    # El error de Python debe indicar que faltan los métodos abstractos
    assert "Can't instantiate abstract class IALauncherBase" in str(exc.value)

# ==============================================================================
# 2. VALIDACIÓN DEL CONTRATO (HERENCIA)
# ==============================================================================

def test_subclase_incompleta_falla():
    """
    Simula el error de un desarrollador que crea un nuevo modelo pero olvida 
    implementar la lógica de ejecución.
    """
    class ModeloIncompleto(IALauncherBase):
        pass

    with pytest.raises(TypeError):
        ModeloIncompleto()

def test_subclase_correcta_cumple_contrato():
    """
    Verifica que una implementación válida puede ser instanciada y 
    llamada siguiendo la firma de tipos definida.
    """
    class ModeloCorrecto(IALauncherBase):
        def ejecutar_modo(self, modo_nombre, imagen_path, config=None, prefijo=""):
            return "path/resultado.jpg", {"status": "ok"}

    instancia = ModeloCorrecto()
    ruta, metadata = instancia.ejecutar_modo("test", "/tmp/img.jpg")
    
    assert ruta == "path/resultado.jpg"
    assert metadata["status"] == "ok"