from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from config import Config

# Inicializamos el objeto de la base de datos (sin vincularlo a la app todavía)
db = SQLAlchemy()
jwt = JWTManager()

def create_app(config_class=Config):
    # Creamos la instancia de Flask
    app = Flask(__name__)
    
    # Cargamos la configuración desde nuestro archivo config.py
    app.config.from_object(config_class)
    
    # Inicializar las extensiones con la app
    db.init_app(app)
    jwt.init_app(app)
    
    # Registro de los Blueprints (Controladores)
    from app.controllers.pipeline_controller import pipeline_bp
    app.register_blueprint(pipeline_bp, url_prefix='/api/v1')

    from app.controllers.auth_controller import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')

    from app.controllers.shop_controller import shop_bp
    app.register_blueprint(shop_bp, url_prefix='/api/v1/shop')

    # --- RUTAS DE LA INTERFAZ WEB ---
    @app.route('/')
    def index():
        return render_template('public/index.html')

    @app.route('/login')
    def login_page():
        return render_template('public/login.html')

    @app.route('/registro')
    def registro_page():
        return render_template('public/registro.html')

    @app.route('/dashboard')
    def dashboard():
        return render_template('dashboard/usuario_panel.html') 
    
    @app.route('/perfil')
    def vista_perfil():
        return render_template('dashboard/perfil.html')

    @app.route('/admin')
    def admin_panel():
        return render_template('admin/admin_panel.html')
    
    @app.route('/shop')
    def shop_view():
        return render_template('dashboard/shop.html')
    
    @app.route('/mis-compras')
    def mis_compras_view():
        return render_template('dashboard/mis_compras.html')
    
    @app.route('/guia-compra')
    def guia_compra_view():
        return render_template('dashboard/guia_compra.html')

    # Importar los modelos para que SQLAlchemy los reconozca al iniciar
    with app.app_context():
        from app import models

    return app