import os
import sys
import io
from pathlib import Path

# -------------------------------------------------------------------
# CONFIGURACIÓN DE RUTAS PARA QUE PYTHON PUEDA IMPORTAR 'src'
# -------------------------------------------------------------------
# pytest ejecuta los tests desde la carpeta raíz del proyecto, pero a veces
# no incluye automáticamente la ruta del proyecto en el sys.path.
# Este bloque calcula la carpeta raíz (server_demo) y la añade manualmente
# al sys.path para permitir imports como "from src.app import create_app".

CURRENT_DIR = os.path.dirname(__file__)              # Carpeta "tests"
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))  


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

# -------------------------------------------------------------------
# HELPERS PARA TESTS CON CARPETA TEMPORAL
# -------------------------------------------------------------------
def get_client_with_tmp_upload(tmp_path, monkeypatch):
    """
    Crea un cliente de la app pero redirigiendo UPLOAD_FOLDER a tmp_path.
    """
    app = create_app()
    monkeypatch.setitem(app.config, "UPLOAD_FOLDER", tmp_path)
    client = app.test_client()
    return client, app, tmp_path


# -------------------------------------------------------------------
# TEST 4: subir imagen OK
# -------------------------------------------------------------------
def test_upload_image_ok(tmp_path, monkeypatch):
    client, app, upload_dir = get_client_with_tmp_upload(tmp_path, monkeypatch)

    data = {
        "image": (io.BytesIO(b"fake-image-data"), "test.png")
    }

    response = client.post(
        "/api/upload_image",
        data=data,
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    body = response.get_json()
    assert "filename" in body

    saved_file = upload_dir / body["filename"]
    assert saved_file.exists()


# -------------------------------------------------------------------
# TEST 5: subir imagen sin campo 'image' -> 400
# -------------------------------------------------------------------
def test_upload_image_missing_field(tmp_path, monkeypatch):
    client, _, _ = get_client_with_tmp_upload(tmp_path, monkeypatch)

    response = client.post(
        "/api/upload_image",
        data={},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    body = response.get_json()
    assert "error" in body


# -------------------------------------------------------------------
# TEST 6: listar imágenes
# -------------------------------------------------------------------
def test_list_images(tmp_path, monkeypatch):
    client, _, upload_dir = get_client_with_tmp_upload(tmp_path, monkeypatch)

    # Crear dos archivos de imagen "falsos"
    (upload_dir / "a.png").write_bytes(b"a")
    (upload_dir / "b.jpg").write_bytes(b"b")

    response = client.get("/api/images")
    assert response.status_code == 200

    images = response.get_json()
    filenames = {img["filename"] for img in images}
    assert filenames == {"a.png", "b.jpg"}


# -------------------------------------------------------------------
# TEST 7: borrar imagen existente
# -------------------------------------------------------------------
def test_delete_existing_image(tmp_path, monkeypatch):
    client, _, upload_dir = get_client_with_tmp_upload(tmp_path, monkeypatch)

    f = upload_dir / "to_delete.png"
    f.write_bytes(b"xxx")

    response = client.delete("/api/images/to_delete.png")
    assert response.status_code == 200

    assert not f.exists()


# -------------------------------------------------------------------
# TEST 8: borrar imagen inexistente -> 404
# -------------------------------------------------------------------
def test_delete_nonexistent_image(tmp_path, monkeypatch):
    client, _, _ = get_client_with_tmp_upload(tmp_path, monkeypatch)

    response = client.delete("/api/images/no_existe.png")
    assert response.status_code == 404


# -------------------------------------------------------------------
# TEST 9: descargar imagen
# -------------------------------------------------------------------
def test_download_image(tmp_path, monkeypatch):
    client, _, upload_dir = get_client_with_tmp_upload(tmp_path, monkeypatch)

    f = upload_dir / "download_me.png"
    content = b"abcdef"
    f.write_bytes(content)

    response = client.get("/api/images/download_me.png/download")
    assert response.status_code == 200
    assert response.data == content


# -------------------------------------------------------------------
# TEST 10: /api/status
# -------------------------------------------------------------------
def test_status_endpoint(tmp_path, monkeypatch):
    client, app, upload_dir = get_client_with_tmp_upload(tmp_path, monkeypatch)

    # Ponemos alguna imagen para que cuente algo
    (upload_dir / "a.png").write_bytes(b"a")

    response = client.get("/api/status")
    assert response.status_code == 200

    body = response.get_json()
    assert body["status"] == "ok"
    assert body["num_images"] == 1
    assert "python_version" in body