from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from app.models import Usuario  # ¡Fíjate! Vuelve a estar súper limpio, solo necesitamos Usuario.

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    datos = request.get_json()
    email = datos.get('email')
    password_plana = datos.get('password')

    if not email or not password_plana:
        return jsonify({"mensaje": "Faltan credenciales"}), 400

    usuario = Usuario.query.filter_by(email=email).first()

    if usuario and usuario.check_password(password_plana):
        
        # 1. Obtenemos los roles gracias a la relación
        lista_roles = [rol.nombre for rol in usuario.roles]
        
        # 2. Obtenemos el plan usando pura lógica de Python y tus nuevas relaciones
        nombre_plan = "basico" # Valor por defecto
        
        # Buscamos en su lista de suscripciones (usuario.suscripciones) la que esté activa
        # next() encuentra el primer elemento que cumpla la condición de forma súper eficiente
        suscripcion_activa = next((s for s in usuario.suscripciones if s.activo), None)
        
        if suscripcion_activa and suscripcion_activa.plan:
            # Si tiene suscripción activa, SQLAlchemy saca el nombre del plan solo
            nombre_plan = suscripcion_activa.plan.nombre.lower() 
        
        # 3. Metemos los datos extra en el token
        datos_extra = {
            "roles": lista_roles,
            "plan": nombre_plan
        }
        
        token = create_access_token(
            identity=str(usuario.id_usuario), 
            additional_claims=datos_extra
        )
        
        return jsonify({
            "status": "success",
            "mensaje": "Login exitoso", 
            "token": token,
            "usuario": usuario.nombre_visible,
            "roles": lista_roles,
            "plan": nombre_plan
        }), 200
        
    else:
        return jsonify({"mensaje": "Email o contraseña incorrectos"}), 401