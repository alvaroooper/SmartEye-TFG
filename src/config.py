import os
from datetime import timedelta
from dotenv import load_dotenv

# Carga de variables de entorno desde el archivo .env
load_dotenv()

class Config:
    """
    Configuración centralizada de la aplicación.
    Define los parámetros de seguridad, persistencia y comportamiento 
    de los módulos integrados (Flask, JWT y SQLAlchemy).
    """

    # ==========================================================================
    # 1. CONFIGURACIÓN BASE Y SEGURIDAD DE SESIÓN
    # ==========================================================================
    # Clave de cifrado para la firma de cookies de sesión y protección CSRF.
    SECRET_KEY = os.environ.get('SECRET_KEY')

    # ==========================================================================
    # 2. PROTOCOLO DE AUTENTICACIÓN (JWT)
    # ==========================================================================
    # Clave privada para la generación y validación de tokens de acceso (JWT).
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    
    # Tiempo de vigencia de los tokens de acceso antes de requerir renovación.
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)

    # ==========================================================================
    # 3. PERSISTENCIA DE DATOS (DATABASE)
    # ==========================================================================
    # URI de conexión al motor de base de datos (MariaDB/SQLite).
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    # Deshabilitación del sistema de eventos de modificación para optimizar 
    # el consumo de memoria y el rendimiento en el servidor.
    SQLALCHEMY_TRACK_MODIFICATIONS = False