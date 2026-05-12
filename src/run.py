from app import create_app

# Inicialización de la instancia de aplicación
app = create_app()

if __name__ == '__main__':
    """
    Punto de entrada principal del servidor.
    - host '0.0.0.0': Permite la escucha en todas las interfaces de red locales.
    - port 5000: Puerto estándar de comunicación para el servicio.
    - debug: Habilitado para facilitar el desarrollo y hot-reloading.
    """
    app.run(debug=True, host='0.0.0.0', port=5000)