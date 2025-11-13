import os
from dotenv import load_dotenv # type: ignore

# Carga el archivo .env
load_dotenv()

class Config:
    DEBUG = os.getenv("DEBUG", "True") == "True"
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))
