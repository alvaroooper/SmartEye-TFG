import pytest
from app import create_app, db
from app.models import Rol


class TestConfig:
    TESTING = True

    # Base de datos aislada para pruebas.
    # No afecta a la base de datos real del proyecto.
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Desactivación de CSRF únicamente en entorno de pruebas automatizadas.
    # Los tests validan la lógica de API, autenticación, permisos y persistencia,
    # no el envío de tokens CSRF desde formularios HTML.
    WTF_CSRF_ENABLED = False

    # Claves fijas únicamente para entorno de test.
    SECRET_KEY = 'test_secret'
    JWT_SECRET_KEY = 'test_jwt_secret_super_larga_de_32_caracteres'


@pytest.fixture
def app():
    """Crea una instancia limpia de la aplicación para cada test."""
    app = create_app(config_class=TestConfig)

    with app.app_context():
        db.create_all()

        # Roles base compartidos por los tests.
        # Muchos tests generan usuarios normales y administradores.
        rol_admin = Rol(id_rol=1, nombre='admin')
        rol_usuario = Rol(id_rol=2, nombre='usuario')

        db.session.add_all([rol_admin, rol_usuario])
        db.session.commit()

        yield app

        # Limpieza completa tras cada test para evitar contaminación entre pruebas.
        db.session.rollback()
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Cliente de pruebas para simular peticiones HTTP contra Flask."""
    return app.test_client()


@pytest.fixture
def db_session(app):
    """Sesión de base de datos reutilizable dentro de los tests."""
    yield db.session