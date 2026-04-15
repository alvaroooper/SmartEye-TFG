from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt, get_jwt_identity
from app.models import Usuario, Rol # Clases en CamelCase según models.py 
from app import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Registra un nuevo usuario y le asigna el rol de 'usuario' por defecto.
    """
    datos = request.get_json()
    username = datos.get('username')
    email = datos.get('email')
    password_plana = datos.get('password')
    nombre_visible = datos.get('nombre_visible', username)

    if Usuario.query.filter_by(email=email).first():
        return jsonify({"status": "error", "mensaje": "El email ya está registrado"}), 400

    # 1. Creamos la instancia del modelo 
    nuevo_usuario = Usuario(
        username=username,
        email=email,
        nombre_visible=nombre_visible
    )
    
    # 2. USAMOS EL HASH: Llamamos al método definido en models.py 
    # Esto ejecuta internamente generate_password_hash 
    nuevo_usuario.set_password(password_plana)

    # 3. Asignamos el rol 'usuario' (nombre en la BD según schema.sql)
    rol_estandar = Rol.query.filter_by(nombre='usuario').first()
    if rol_estandar:
        nuevo_usuario.roles.append(rol_estandar)

    try:
        lista_roles = [rol.nombre for rol in nuevo_usuario.roles]
        token = create_access_token(
            identity=str(nuevo_usuario.id_usuario),
            additional_claims={"roles": lista_roles}
        )

        return jsonify({
            "status": "success",
            "mensaje": "Usuario creado correctamente",
            "token": token,           # Enviamos el token
            "usuario": nuevo_usuario.nombre_visible,
            "roles": lista_roles      # Enviamos roles para la redirección
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Autentica al usuario y devuelve el token junto con sus roles.
    """
    datos = request.get_json()
    email = datos.get('email')
    password_plana = datos.get('password')

    usuario = Usuario.query.filter_by(email=email).first()

    # USAMOS EL HASH: Llamamos al método check_password de models.py 
    # Esto ejecuta internamente check_password_hash 
    if usuario and usuario.check_password(password_plana):
        # Extraemos nombres de roles (el campo se llama 'nombre' en models.py) [cite: 21]
        lista_roles = [rol.nombre for rol in usuario.roles]
        
        # Generamos el token con roles para que el frontend redirija [cite: 38]
        token = create_access_token(
            identity=str(usuario.id_usuario),
            additional_claims={"roles": lista_roles}
        )

        return jsonify({
            "status": "success",
            "token": token,
            "usuario": usuario.nombre_visible,
            "roles": lista_roles
        }), 200

    return jsonify({"status": "error", "mensaje": "Email o contraseña incorrectos"}), 401

@auth_bp.route('/usuarios', methods=['GET'])
@jwt_required()
def listar_usuarios():
    # Verificamos si el usuario es admin desde los claims del token
    claims = get_jwt()
    if 'admin' not in claims.get('roles', []):
        return jsonify({"mensaje": "Acceso restringido a administradores"}), 403

    usuarios = Usuario.query.all()
    resultado = []
    for u in usuarios:
        resultado.append({
            "id": u.id_usuario,
            "nombre": u.nombre_visible,
            "email": u.email,
            "roles": [rol.nombre for rol in u.roles]
        })
    
    return jsonify(resultado), 200