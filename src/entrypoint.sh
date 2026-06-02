#!/bin/sh
set -e

echo "Preparando carpetas necesarias..."

mkdir -p /app/execution_data
mkdir -p /app/models/mp
mkdir -p /app/models/yolo
mkdir -p /tmp/matplotlib
mkdir -p /tmp/ultralytics

if ! mkdir -p /app/execution_data/.permiso_test; then
    echo "ERROR: La aplicación no tiene permisos de escritura en /app/execution_data."
    exit 1
fi
rmdir /app/execution_data/.permiso_test

if ! mkdir -p /app/models/.permiso_test; then
    echo "ERROR: La aplicación no tiene permisos de escritura en /app/models."
    exit 1
fi
rmdir /app/models/.permiso_test

echo "Esperando a que MariaDB esté disponible..."

python - <<'PY'
import os
import time
import pymysql
from urllib.parse import urlparse, unquote

database_url = os.environ.get("DATABASE_URL")

if not database_url:
    print("ERROR: DATABASE_URL no está definida.")
    raise SystemExit(1)

parsed = urlparse(database_url)

host = parsed.hostname
port = parsed.port or 3306
user = unquote(parsed.username or "")
password = unquote(parsed.password or "")
database = parsed.path.lstrip("/")

for intento in range(1, 41):
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset="utf8mb4"
        )
        conn.close()
        print("MariaDB disponible.")
        break
    except Exception as exc:
        print(f"Intento {intento}/40: no se pudo conectar con MariaDB. Error: {exc}")
        time.sleep(2)
else:
    print("ERROR: No se pudo conectar con MariaDB.")
    raise SystemExit(1)
PY

if [ "$#" -gt 0 ]; then
    echo "Ejecutando comando personalizado: $@"
    exec "$@"
fi

echo "Arrancando aplicación Flask con Gunicorn..."

exec gunicorn --workers 1 --bind 0.0.0.0:5000 --timeout 300 run:app