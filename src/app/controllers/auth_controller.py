import os
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt, get_jwt_identity

from app import db
from app.models import Usuario, Rol, Ejecucion, TemporalArchivo, SuscripcionPlan, Alquila, TipoPlan

auth_bp = Blueprint('auth', __name__)

# ==============================================================================
# FUNCIONES AUXILIARES DE SEGURIDAD
# ==============================================================================

def validar_password_segura(password):
    """
    Evalúa la robustez de una contraseña según los estándares de seguridad actuales.
    Retorna una tupla: (Es_Valida: bool, Mensaje_Error: str)
    """
    if len(password) < 8:
        return False, "La contraseña debe tener al menos 8 caracteres."
    if not any(c.islower() for c in password):
        return False, "La contraseña debe contener al menos una letra minúscula."
    if not any(c.isupper() for c in password):
        return False, "La contraseña debe contener al menos una letra mayúscula."
    if not any(c.isdigit() for c in password):
        return False, "La contraseña debe contener al menos un número."
        
    return True, ""


# ==============================================================================
# GESTIÓN DE AUTENTICACIÓN (LOGIN Y REGISTRO)
# ==============================================================================

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Registra un nuevo usuario en el sistema, aplica el hash de seguridad a la contraseña,
    le asigna el rol base ('usuario') y le otorga el Plan Básico gratuito por defecto.
    """
    datos = request.get_json()
    username = datos.get('username')
    email = datos.get('email')
    password_plana = datos.get('password')
    nombre_visible = datos.get('nombre_visible', username)

    if Usuario.query.filter_by(email=email).first():
        return jsonify({"status": "error", "mensaje": "El email ya se encuentra registrado."}), 400

    # --- NUEVA VALIDACIÓN DE CONTRASEÑA ROBUSTA ---
    es_valida, msg_error = validar_password_segura(password_plana)
    if not es_valida:
        return jsonify({"status": "error", "mensaje": msg_error}), 400
    # ----------------------------------------------

    nuevo_usuario = Usuario(
        username=username,
        email=email,
        nombre_visible=nombre_visible,
        estado='activa' # Estado inicial por defecto
    )
    
    # Encriptación de contraseña a través del modelo
    nuevo_usuario.set_password(password_plana)

    # Asignación de permisos base
    rol_estandar = Rol.query.filter_by(nombre='usuario').first()
    if rol_estandar:
        nuevo_usuario.roles.append(rol_estandar)

    try:
        db.session.add(nuevo_usuario)
        db.session.flush() # Sincroniza temporalmente para obtener el id_usuario autogenerado

        # Asignación de plan de suscripción inicial
        plan_basico = TipoPlan.query.filter_by(nombre='Basico').first()
        if plan_basico:
            nueva_sub = SuscripcionPlan(
                id_usuario=nuevo_usuario.id_usuario,
                id_plan=plan_basico.id_plan,
                activo=1,
                renovacion_auto=0,
                importe=0.00,
                fecha_fin=None # Acceso permanente al nivel básico
            )
            db.session.add(nueva_sub)

        db.session.commit()
        
        # Generación de token JWT para acceso inmediato tras registro
        lista_roles = [rol.nombre for rol in nuevo_usuario.roles]
        token = create_access_token(
            identity=str(nuevo_usuario.id_usuario),
            additional_claims={"roles": lista_roles}
        )

        return jsonify({
            "status": "success",
            "mensaje": "Usuario creado correctamente.",
            "token": token,
            "usuario": nuevo_usuario.nombre_visible,
            "roles": lista_roles
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": f"Error interno en el registro: {str(e)}"}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Valida credenciales de acceso. Incorpora verificación de estado de cuenta
    para bloquear accesos a usuarios eliminados lógicamente o anonimizados.
    """
    datos = request.get_json()
    # Ahora recibimos un identificador único (puede ser email o username)
    identificador = datos.get('identificador')
    password_plana = datos.get('password')

    # Buscamos al usuario que coincida con el email O con el username
    usuario = Usuario.query.filter(
        (Usuario.email == identificador) | (Usuario.username == identificador)
    ).first()

    # Verificamos si existe el usuario y si la contraseña es correcta
    if usuario and usuario.check_password(password_plana):
        # Bloqueo de seguridad para cuentas no activas
        if getattr(usuario, 'estado', 'activa') != 'activa':
            return jsonify({"status": "error", "mensaje": "Esta cuenta está desactivada."}), 403

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

    return jsonify({"status": "error", "mensaje": "Credenciales incorrectas."}), 401
# ==============================================================================
# GESTIÓN DE PERFILES Y ADMINISTRACIÓN
# ==============================================================================

@auth_bp.route('/usuarios', methods=['GET'])
@jwt_required()
def listar_usuarios():
    """
    Endpoint administrativo para obtener el listado completo de usuarios registrados.
    """
    claims = get_jwt()
    if 'admin' not in claims.get('roles', []):
        return jsonify({"mensaje": "Acceso restringido. Se requieren privilegios de administrador."}), 403

    usuarios = Usuario.query.all()
    resultado = []
    for u in usuarios:
        resultado.append({
            "id": u.id_usuario,
            "nombre": u.nombre_visible,
            "email": u.email,
            "estado": getattr(u, 'estado', 'activa'),
            "roles": [rol.nombre for rol in u.roles]
        })
    
    return jsonify(resultado), 200

@auth_bp.route('/perfil', methods=['GET'])
@jwt_required()
def obtener_perfil():
    """
    Recupera los datos actuales del perfil del usuario autenticado.
    """
    usuario_id = get_jwt_identity()
    usuario = Usuario.query.get(usuario_id)
    
    if not usuario:
        return jsonify({"status": "error", "mensaje": "Usuario no encontrado."}), 404
        
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
    Permite a un usuario modificar su nombre mostrado y sus credenciales.
    Valida la integridad de la contraseña actual antes de aplicar cambios.
    """
    usuario_id = get_jwt_identity()
    usuario = Usuario.query.get(usuario_id)
    
    if not usuario:
        return jsonify({"status": "error", "mensaje": "Usuario no encontrado."}), 404
        
    data = request.json
    nuevo_nombre_pantalla = data.get('nombre_visible')
    nueva_password = data.get('password')
    old_password = data.get('old_password')
    
    if nuevo_nombre_pantalla:
        usuario.nombre_visible = nuevo_nombre_pantalla # Se actualiza el campo correcto
        
    if nueva_password:
        if not old_password:
            return jsonify({"status": "error", "mensaje": "Se requiere la contraseña actual para autorizar el cambio."}), 400
            
        if not usuario.check_password(old_password):
            return jsonify({"status": "error", "mensaje": "La contraseña actual introducida no es válida."}), 401
            
        # Validación de robustez de la nueva contraseña
        es_valida, msg_error = validar_password_segura(nueva_password)
        if not es_valida:
            return jsonify({"status": "error", "mensaje": msg_error}), 400
             
        usuario.set_password(nueva_password)
        
    try:
        db.session.commit()
        return jsonify({
            "status": "success", 
            "mensaje": "Perfil actualizado correctamente.", 
            "nuevo_nombre": usuario.nombre_visible
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": f"Error en la actualización: {str(e)}"}), 500

# ==============================================================================
# BORRADO LÓGICO Y CUMPLIMIENTO LEGAL (RGPD)
# ==============================================================================

@auth_bp.route('/cuenta', methods=['DELETE'])
@jwt_required()
def eliminar_cuenta():
    """
    Implementa un Borrado Lógico (Soft Delete) de la cuenta de usuario.
    """
    usuario_id = get_jwt_identity()
    usuario = Usuario.query.get(usuario_id)
    
    if not usuario:
        return jsonify({"status": "error", "mensaje": "Usuario no encontrado en el sistema."}), 404
        
    try:
        usuario.estado = 'borrada'
        usuario.borrado_en = datetime.now()
        
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
            "mensaje": "Su cuenta ha sido desactivada correctamente. Los datos personales serán eliminados de forma definitiva tras finalizar el periodo de retención legal."
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": f"Fallo al procesar la baja de la cuenta: {str(e)}"}), 500
    

@auth_bp.route('/admin/cambiar_estado/<int:id_usuario>', methods=['POST'])
@jwt_required()
def admin_cambiar_estado(id_usuario):
    """
    Permite a un administrador modificar el estado operativo de una cuenta.
    Gestiona el bloqueo (borrado lógico) y la reactivación de usuarios.
    """
    # 1. Verificación de privilegios de administrador
    claims = get_jwt()
    if 'admin' not in claims.get('roles', []):
        return jsonify({"mensaje": "Acceso denegado: Privilegios insuficientes"}), 403
    
    # 2. Localización del sujeto en la base de datos
    usuario = Usuario.query.get(id_usuario)
    if not usuario:
        return jsonify({"mensaje": "Usuario no encontrado"}), 404
        
    # 3. Restricción de seguridad: Un admin no puede desactivarse a sí mismo
    if usuario.id_usuario == int(get_jwt_identity()):
        return jsonify({"mensaje": "Error de integridad: No puedes modificar tu propio estado"}), 400

    # 4. Procesamiento del cambio de estado
    datos = request.get_json()
    nuevo_estado = datos.get('estado') # Valores esperados: 'activa' o 'borrada'
    
    usuario.estado = nuevo_estado
    
    # Si el estado es 'borrada', registramos la fecha para el proceso de anonimización legal (RGPD)
    # Usamos timezone.utc para mantener la consistencia con el resto del sistema
    usuario.borrado_en = datetime.now(timezone.utc) if nuevo_estado == 'borrada' else None
    
    try:
        db.session.commit()
        return jsonify({
            "status": "success", 
            "mensaje": f"El estado de '{usuario.username}' se ha actualizado a '{nuevo_estado}' correctamente."
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"mensaje": "Error interno al actualizar la base de datos"}), 500