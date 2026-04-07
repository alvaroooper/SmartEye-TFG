from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

# Inicializamos el objeto de la base de datos (sin vincularlo a la app todavía)
db = SQLAlchemy()

def create_app(config_class=Config):
    # Creamos la instancia de Flask
    app = Flask(__name__)
    
    # Cargamos la configuración desde nuestro archivo config.py
    app.config.from_object(config_class)
    
    # Vinculamos la base de datos a esta aplicación
    db.init_app(app)
    
    # IMPORTANTE: Aquí registramos los Blueprints (Controladores)
    from app.controllers.pipeline_controller import pipeline_bp
    app.register_blueprint(pipeline_bp, url_prefix='/api/v1')

    # Importamos los modelos para que SQLAlchemy los reconozca al iniciar
    with app.app_context():
        from app import models
        
        # Opcional: Si quieres que Flask cree las tablas automáticamente
        # db.create_all() 

    return app