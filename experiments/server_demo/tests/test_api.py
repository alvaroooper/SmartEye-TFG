import os
import sys

# -------------------------------------------------------------------
# CONFIGURACIÓN DE RUTAS PARA QUE PYTHON PUEDA IMPORTAR 'src'
# -------------------------------------------------------------------
# pytest ejecuta los tests desde la carpeta raíz del proyecto, pero a veces
# no incluye automáticamente la ruta del proyecto en el sys.path.
# Este bloque calcula la carpeta raíz (server_demo) y la añade manualmente
# al sys.path para permitir imports como "from src.app import create_app".

CURRENT_DIR = os.path.dirname(__file__)              # Carpeta "tests"
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))  
# Ahora PROJECT_ROOT apunta a la carpeta "server_demo"

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Ahora ya podemos importar create_app sin errores
from src.app import create_app # type: ignore


# -------------------------------------------------------------------
# FUNCIÓN AUXILIAR PARA CREAR UN CLIENTE DE PRUEBAS DE FLASK
# -------------------------------------------------------------------
def get_client():
    """
    Crea una instancia de la aplicación Flask en modo de pruebas
    y devuelve un cliente de testing.
    
    Este cliente permite hacer peticiones GET/POST/etc. sin levantar
    un servidor real, todo se ejecuta en memoria.
    """
    app = create_app()
    return app.test_client()


# -------------------------------------------------------------------
# TEST 1: COMPROBAR QUE EL ENDPOINT /api/health FUNCIONA CORRECTAMENTE
# -------------------------------------------------------------------
def test_health_endpoint():
    """
    Verifica que el endpoint /api/health:
    - responde con código 200 (OK)
    - devuelve un JSON con la clave "status" = "ok"
    """

    client = get_client()

    # Simulamos una petición GET a la ruta /api/health
    response = client.get("/api/health")

    # Comprobamos que la respuesta es correcta
    assert response.status_code == 200

    # Obtenemos el JSON devuelto por el servidor
    data = response.get_json()

    # Validamos el contenido esperado
    assert data["status"] == "ok"


# -------------------------------------------------------------------
# TEST 2: COMPROBAR QUE UNA RUTA INEXISTENTE DEVUELVE 404
# -------------------------------------------------------------------
def test_not_found():
    """
    Verifica que si el cliente intenta acceder a una ruta que no existe,
    como /ruta_que_no_existe, el servidor devuelve un código 404 (Not Found).
    """

    client = get_client()

    # Petición a una ruta inexistente
    response = client.get("/ruta_que_no_existe")

    # El servidor debe responder con 404
    assert response.status_code == 404


# -------------------------------------------------------------------
# TEST 3: COMPROBAR QUE UN MÉTODO NO PERMITIDO DEVUELVE 405
# -------------------------------------------------------------------
def test_method_not_allowed():
    """
    Verifica que si se intenta utilizar un método HTTP no permitido
    (por ejemplo, POST en un endpoint que solo admite GET),
    Flask devuelve un código 405 (Method Not Allowed).
    """

    client = get_client()

    # Intentamos enviar una petición POST a un endpoint que solo acepta GET
    response = client.post("/api/health")

    # El servidor debe devolver 405 automáticamente
    assert response.status_code == 405
