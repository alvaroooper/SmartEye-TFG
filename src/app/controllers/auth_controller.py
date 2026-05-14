from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt, get_jwt_identity

from app import db
from app.models import Usuario, Rol, SuscripcionPlan, Alquila, TipoPlan

auth_bp = Blueprint('auth', __name__)

# ==============================================================================
# SERVICIOS DE VALIDACIÓN Y CRIPTOGRAFÍA
# ==============================================================================

def validar_password_segura(password: str) -> tuple[bool, str]:
    """
    Evalúa la entropía y robustez de la credencial según normativas de seguridad (OWASP).
    Exige longitud mínima, cardinalidad mixta (mayúsculas/minúsculas) y alfanumérica.
    """
    if len(password) < 8:
        return False, "La contraseña debe tener una longitud mínima de 8 caracteres."
    if not any(c.islower() for c in password):
        return False, "La contraseña requiere al menos un carácter en minúscula."
    if not any(c.isupper() for c in password):
        return False, "La contraseña requiere al menos un carácter en mayúscula."
    if not any(c.isdigit() for c in password):
        return False, "La contraseña requiere al menos un carácter numérico."
        
    return True, ""

# ==============================================================================
# MÓDULO DE AUTENTICACIÓN Y APROVISIONAMIENTO
# ==============================================================================

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Aprovisionamiento de nuevas identidades en el sistema.
    Aplica hashing criptográfico a la contraseña, asocia el perfil de acceso base (RBAC) 
    y genera el contrato de suscripción comercial por defecto (Plan Básico).
    """
    datos = request.get_json()
    username = datos.get('username')
    email = datos.get('email')
    password_plana = datos.get('password')
    nombre_visible = datos.get('nombre_visible', username)

    # Control de unicidad de identidades
    if Usuario.query.filter_by(email=email).first():
        return jsonify({"status": "error", "mensaje": "La dirección de correo ya consta en el sistema."}), 400

    if Usuario.query.filter_by(username=username).first():
        return jsonify({"status": "error", "mensaje": "El nombre de usuario ya está en uso."}), 400         
    
    if not username or not email or not password_plana:
        return jsonify({
            "status": "error", 
            "mensaje": "Payload incompleto. Los campos 'username', 'email' y 'password' son obligatorios."
        }), 400
    
    es_valida, msg_error = validar_password_segura(password_plana)
    if not es_valida:
        return jsonify({"status": "error", "mensaje": msg_error}), 400

    nuevo_usuario = Usuario(
        username=username,
        email=email,
        nombre_visible=nombre_visible,
        estado='activa'
    )
    
    nuevo_usuario.set_password(password_plana)

    rol_estandar = Rol.query.filter_by(nombre='usuario').first()
    if rol_estandar:
        nuevo_usuario.roles.append(rol_estandar)

    try:
        db.session.add(nuevo_usuario)
        db.session.flush() # Sincronización intermedia para obtener la clave primaria (ID)

        plan_basico = TipoPlan.query.filter_by(nombre='Basico').first()
        if plan_basico:
            nueva_sub = SuscripcionPlan(
                id_usuario=nuevo_usuario.id_usuario,
                id_plan=plan_basico.id_plan,
                activo=1,
                renovacion_auto=0,
                importe=0.00,
                fecha_fin=None 
            )
            db.session.add(nueva_sub)

        db.session.commit()
        
        # Generación de token JWT para establecimiento de sesión inmediata
        lista_roles = [rol.nombre for rol in nuevo_usuario.roles]
        token = create_access_token(
            identity=str(nuevo_usuario.id_usuario),
            additional_claims={"roles": lista_roles}
        )

        return jsonify({
            "status": "success",
            "mensaje": "Identidad aprovisionada correctamente.",
            "token": token,
            "usuario": nuevo_usuario.nombre_visible,
            "roles": lista_roles
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": f"Fallo de integridad durante el registro: {str(e)}"}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Validación de credenciales y expedición de tokens de sesión (JWT).
    Implementa restricciones de acceso basadas en el estado lógico de la cuenta.
    """
    datos = request.get_json()
    identificador = datos.get('identificador')
    password_plana = datos.get('password')

    usuario = Usuario.query.filter(
        (Usuario.email == identificador) | (Usuario.username == identificador)
    ).first()

    if usuario and usuario.check_password(password_plana):
        # Bloqueo de autenticación para cuentas revocadas o bajo investigación
        if getattr(usuario, 'estado', 'activa') != 'activa':
            return jsonify({"status": "error", "mensaje": "Acceso denegado: Identidad desactivada o bloqueada."}), 403

        lista_roles = [rol.nombre for rol in usuario.roles]
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

    return jsonify({"status": "error", "mensaje": "Fallo de autenticación: Credenciales inválidas."}), 401

# ==============================================================================
# GESTIÓN DE PERFILES Y CONTROL ADMINISTRATIVO
# ==============================================================================

@auth_bp.route('/usuarios', methods=['GET'])
@jwt_required()
def listar_usuarios():
    """
    Endpoint de auditoría global para obtención del catálogo de identidades.
    Restringido a perfiles con privilegios administrativos.
    """
    claims = get_jwt()
    if 'admin' not in claims.get('roles', []):
        return jsonify({"mensaje": "Violación de acceso: Privilegios insuficientes."}), 403

    usuarios = Usuario.query.all()
    resultado = [{
        "id": u.id_usuario,
        "nombre": u.nombre_visible,
        "username": u.username,
        "email": u.email,
        "estado": getattr(u, 'estado', 'activa'),
        "roles": [rol.nombre for rol in u.roles]
    } for u in usuarios]
    
    return jsonify(resultado), 200

@auth_bp.route('/perfil', methods=['GET'])
@jwt_required()
def obtener_perfil():
    """Recuperación de los metadatos de perfil vinculados al token activo."""
    usuario_id = get_jwt_identity()
    usuario = db.session.get(Usuario, usuario_id)
    
    if not usuario:
        return jsonify({"status": "error", "mensaje": "Identidad no localizada en el sistema."}), 404
        
    return jsonify({
        "status": "success",
        "datos": {
            "username": usuario.username,
            "email": usuario.email,
            "nombre_visible": usuario.nombre_visible,
            "fecha_registro": usuario.creado_en.strftime("%d/%m/%Y")
        }
    }), 200

@auth_bp.route('/perfil', methods=['PUT'])
@jwt_required()
def actualizar_perfil():
    """
    Modificación de atributos de perfil y actualización de credenciales.
    Exige validación de la credencial vigente para autorizar la mutación del hash.
    """
    usuario_id = get_jwt_identity()
    usuario = db.session.get(Usuario, usuario_id)
    
    if not usuario:
        return jsonify({"status": "error", "mensaje": "Identidad no localizada."}), 404
        
    data = request.json
    nuevo_nombre_pantalla = data.get('nombre_visible')
    nueva_password = data.get('password')
    old_password = data.get('old_password')
    
    if nuevo_nombre_pantalla:
        usuario.nombre_visible = nuevo_nombre_pantalla 
        
    if nueva_password:
        if not old_password:
            return jsonify({"status": "error", "mensaje": "Autenticación requerida para modificar credenciales."}), 400
            
        if not usuario.check_password(old_password):
            return jsonify({"status": "error", "mensaje": "La contraseña actual no coincide con los registros."}), 401
            
        es_valida, msg_error = validar_password_segura(nueva_password)
        if not es_valida:
            return jsonify({"status": "error", "mensaje": msg_error}), 400
             
        usuario.set_password(nueva_password)
        
    try:
        db.session.commit()
        return jsonify({
            "status": "success", 
            "mensaje": "Atributos de identidad actualizados con éxito.", 
            "nuevo_nombre": usuario.nombre_visible
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": f"Fallo de persistencia: {str(e)}"}), 500


# ==============================================================================
# AUDITORÍA LEGAL, RETENCIÓN DE DATOS Y CUMPLIMIENTO (RGPD)
# ==============================================================================

@auth_bp.route('/cuenta', methods=['DELETE'])
@jwt_required()
def eliminar_cuenta():
    """
    Ejecuta el protocolo de Baja Lógica (Soft Delete) solicitado por el cliente.
    Revoca inmediatamente servicios activos, contratos y marca la fecha base 
    para la posterior anonimización exigida por el RGPD.
    """
    usuario_id = get_jwt_identity()
    usuario = db.session.get(Usuario, usuario_id)
    
    if not usuario:
        return jsonify({"status": "error", "mensaje": "Identidad no localizada."}), 404
        
    try:
        usuario.estado = 'borrada'
        usuario.borrado_en = datetime.now(timezone.utc).replace(tzinfo=None)
        
        SuscripcionPlan.query.filter_by(id_usuario=usuario_id, activo=1).update({
            "activo": 0, 
            "renovacion_auto": 0
        })
        
        Alquila.query.filter_by(id_usuario=usuario_id, activo=1).update({
            "activo": 0, 
            "renovacion_auto": 0
        })

        db.session.commit()
        
        return jsonify({
            "status": "success", 
            "mensaje": "Baja de servicio procesada. Retención de datos activa según periodo legal."
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": f"Fallo en la revocación de cuenta: {str(e)}"}), 500
    

@auth_bp.route('/admin/cambiar_estado/<int:id_usuario>', methods=['POST'])
@jwt_required()
def admin_cambiar_estado(id_usuario):
    """
    Protocolo de bloqueo/reactivación administrativa.
    Altera el estado lógico de una cuenta, impidiendo o restaurando su capacidad de acceso.
    """
    claims = get_jwt()
    if 'admin' not in claims.get('roles', []):
        return jsonify({"mensaje": "Violación de acceso: Acción reservada a administradores."}), 403
    
    usuario = db.session.get(Usuario, id_usuario)
    if not usuario:
        return jsonify({"mensaje": "Identidad objetivo no localizada."}), 404
        
    # Prevención de auto-bloqueo accidental
    if usuario.id_usuario == int(get_jwt_identity()):
        return jsonify({"mensaje": "Restricción de sistema: Imposible alterar el estado de la cuenta propia."}), 400

    datos = request.get_json()
    nuevo_estado = datos.get('estado')
    
    usuario.estado = nuevo_estado
    usuario.borrado_en = datetime.now(timezone.utc).replace(tzinfo=None) if nuevo_estado == 'borrada' else None
    
    try:
        db.session.commit()
        return jsonify({
            "status": "success", 
            "mensaje": f"Estado operativo de '{usuario.username}' modificado a '{nuevo_estado}'."
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"mensaje": "Fallo de actualización en la base de datos."}), 500
    