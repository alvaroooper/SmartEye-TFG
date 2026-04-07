import os

class Config:
    # Clave secreta para sesiones y seguridad (cámbiar en producción)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta-para-el-tfg-123'
    
    # Configuración de la conexión a MariaDB
    # Formato: mysql+pymysql://usuario:contraseña@servidor:puerto/nombre_bd
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://tfg_user:tfg2026@localhost:3306/tfg_db'
    
    # Desactiva una característica de Flask-SQLAlchemy que consume mucha memoria y no necesitamos
    SQLALCHEMY_TRACK_MODIFICATIONS = False