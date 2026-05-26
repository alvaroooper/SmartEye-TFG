from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_wtf.csrf import CSRFProtect, CSRFError
from config import Config

# ==============================================================================
# INICIALIZACIÓN DE EXTENSIONES GLOBALES
# ==============================================================================
# Se instancian los objetos de persistencia y seguridad fuera del factory para
# permitir su acceso global, vinculándolos dinámicamente en el tiempo de ejecución.
db = SQLAlchemy()
jwt = JWTManager()
csrf = CSRFProtect()


def create_app(config_class=Config):
    """
    Factoría de la aplicación (Application Factory Pattern).
    Encargada de la configuración del entorno, inicialización de componentes,
    registro de controladores y definición de la capa de presentación.
    """
    app = Flask(__name__)

    # Carga de la configuración del sistema
    app.config.from_object(config_class)

    # Inicialización de extensiones bajo el contexto de la aplicación
    db.init_app(app)
    jwt.init_app(app)
    csrf.init_app(app)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        """
        Gestión homogénea de errores CSRF.

        En las rutas API se devuelve una respuesta JSON para mantener el contrato
        de comunicación con el frontend. En el resto de casos se informa igualmente
        del rechazo de la petición.
        """
        return jsonify({
            "status": "error",
            "mensaje": "Token CSRF ausente o inválido.",
            "detalle": error.description
        }), 400

    # ==========================================================================
    # REGISTRO DE MÓDULOS (BLUEPRINTS) - CONTROLADORES API
    # ==========================================================================
    # Se realiza la importación local para evitar dependencias circulares.
    from app.controllers.pipeline_controller import pipeline_bp
    app.register_blueprint(pipeline_bp, url_prefix='/api/v1')

    from app.controllers.auth_controller import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')

    from app.controllers.shop_controller import shop_bp
    app.register_blueprint(shop_bp, url_prefix='/api/v1/shop')

    # ==========================================================================
    # DEFINICIÓN DE RUTAS: INTERFAZ WEB (FRONTEND)
    # ==========================================================================

    @app.route('/', methods=['GET'])
    def index():
        """Página de inicio pública."""
        return render_template('public/index.html')

    @app.route('/login', methods=['GET'])
    def login_page():
        """Punto de acceso de usuarios."""
        return render_template('public/login.html')

    @app.route('/registro', methods=['GET'])
    def registro_page():
        """Formulario de alta de nuevos usuarios."""
        return render_template('public/registro.html')

    @app.route('/dashboard', methods=['GET'])
    def dashboard():
        """Panel principal de usuario autenticado."""
        return render_template('dashboard/usuario_panel.html')

    @app.route('/perfil', methods=['GET'])
    def vista_perfil():
        """Gestión de cuenta y configuración de usuario."""
        return render_template('dashboard/perfil.html')

    @app.route('/admin', methods=['GET'])
    def admin_panel():
        """Consola de administración y auditoría del sistema."""
        return render_template('admin/admin_panel.html')

    @app.route('/shop', methods=['GET'])
    def shop_view():
        """Marketplace de servicios y modelos de IA."""
        return render_template('dashboard/shop.html')

    @app.route('/mis-compras', methods=['GET'])
    def mis_compras_view():
        """Listado de servicios contratados por el usuario."""
        return render_template('dashboard/mis_compras.html')

    @app.route('/guia-compra', methods=['GET'])
    def guia_compra_view():
        """Manual de usuario y guía técnica de adquisición."""
        return render_template('dashboard/guia_compra.html')

    @app.route('/historial', methods=['GET'])
    def historial_view():
        """Registro histórico de ejecuciones realizadas."""
        return render_template('dashboard/historial.html')

    @app.route('/resultados/<int:id_ejecucion>', methods=['GET'])
    def resultados_view(id_ejecucion):
        """Vista detallada de los resultados de un proceso específico."""
        return render_template('dashboard/resultados_ejecucion.html', id_ejecucion=id_ejecucion)

    # Asegurar el mapeo de los modelos de datos en el contexto de la aplicación
    with app.app_context():
        from app import models

    return app