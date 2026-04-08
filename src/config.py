import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 1. Clave secreta general de Flask (usada internamente por la app)
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # --- 2. NUEVA CONFIGURACIÓN JWT (SEGURIDAD DE LA API) ---
    # Esta es la "firma" de los tokens JWT. Debe ser una cadena larga y secreta para garantizar la seguridad de los tokens. 
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    
    # Caducidad del token (ej: 2 horas). Pasado este tiempo, el usuario debe hacer login de nuevo.
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)
    
    # --- 3. BASE DE DATOS ---
    # Configuración de la conexión a MariaDB
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    # Desactiva el rastreo de modificaciones para ahorrar memoria en el servidor
    SQLALCHEMY_TRACK_MODIFICATIONS = False