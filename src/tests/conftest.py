import pytest
from app import create_app, db
from app.models import Usuario, Rol

class TestConfig:
    TESTING = True
    # Uso de SQLite en memoria para que las pruebas sean rápidas y no afecten a la DB real
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:' 
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test_secret'
    JWT_SECRET_KEY = 'test_jwt_secret_super_larga_de_32_caracteres'

@pytest.fixture
def app():
    """Instancia de la aplicación configurada para pruebas."""
    app = create_app(config_class=TestConfig)
    
    with app.app_context():
        db.create_all()
        # Inyección de los datos base necesarios para todas las pruebas
        rol_usuario = Rol(id_rol=2, nombre='usuario')
        db.session.add(rol_usuario)
        db.session.commit()
        
        yield app
        
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Cliente de pruebas para simular peticiones HTTP."""
    return app.test_client()

@pytest.fixture
def db_session(app):
    """Acceso directo a la sesión de la base de datos."""
    yield db.session

