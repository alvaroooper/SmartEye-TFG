from app import create_app, db

# Creamos la aplicación usando el Factory de app/__init__.py
app = create_app()

if __name__ == '__main__':
    # Ejecutamos en modo debug para desarrollo
    app.run(debug=True, host='0.0.0.0', port=5000)