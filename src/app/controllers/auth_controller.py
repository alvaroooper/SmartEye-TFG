from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt, get_jwt_identity
from app.models import Usuario, Rol, Ejecucion, TemporalArchivo, SuscripcionPlan, Alquila, TipoPlan
from app import db
import os

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
        # 1. Añadimos el usuario y hacemos flush para obtener su ID asignada por la base de datos
        db.session.add(nuevo_usuario)
        db.session.flush() 

        # 2. Buscamos el plan básico y se lo asignamos por defecto
        plan_basico = TipoPlan.query.filter_by(nombre='Basico').first()
        if plan_basico:
            nueva_sub = SuscripcionPlan(
                id_usuario=nuevo_usuario.id_usuario,
                id_plan=plan_basico.id_plan,
                activo=1,
                renovacion_auto=0,
                importe=0.00,
                fecha_fin=None # Acceso de por vida
            )
            db.session.add(nueva_sub)

        # 3. Guardamos todo definitivamente
        db.session.commit()
        
        lista_roles = [rol.nombre for rol in nuevo_usuario.roles]
        token = create_access_token(
            identity=str(nuevo_usuario.id_usuario),
            additional_claims={"roles": lista_roles}
        )

        return jsonify({
            "status": "success",
            "mensaje": "Usuario creado correctamente",
            "token": token,
            "usuario": nuevo_usuario.nombre_visible,
            "roles": lista_roles
        }), 201

    except Exception as e:
        db.session.rollback() # Limpiar la transacción en caso de error
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

@auth_bp.route('/perfil', methods=['PUT'])
@jwt_required()
def actualizar_perfil():
    usuario_id = get_jwt_identity()
    usuario = Usuario.query.get(usuario_id)
    
    if not usuario:
        return jsonify({"status": "error", "mensaje": "Usuario no encontrado"}), 404
        
    data = request.json
    nuevo_nombre = data.get('username')
    nueva_password = data.get('password')
    old_password = data.get('old_password') # <-- Recogemos la contraseña antigua
    
    # 1. Actualizamos el nombre si nos lo han enviado
    if nuevo_nombre:
        usuario.username = nuevo_nombre
        
    # 2. Lógica para cambiar la contraseña
    if nueva_password:
        # Validar que han enviado la antigua
        if not old_password:
            return jsonify({"status": "error", "mensaje": "Debes introducir tu contraseña actual para poder cambiarla"}), 400
            
        # Comprobar que la antigua es correcta
        if not check_password_hash(usuario.password_hash, old_password):
            return jsonify({"status": "error", "mensaje": "La contraseña actual es incorrecta"}), 401
            
        # Comprobar la longitud de la nueva
        if len(nueva_password) < 6:
             return jsonify({"status": "error", "mensaje": "La nueva contraseña debe tener al menos 6 caracteres"}), 400
             
        # Si todo es correcto, la encriptamos y la guardamos
        usuario.password_hash = generate_password_hash(nueva_password)
        
    try:
        db.session.commit()
        return jsonify({"status": "success", "mensaje": "Perfil actualizado", "nuevo_nombre": usuario.username}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": f"Error al actualizar: {str(e)}"}), 500
        
@auth_bp.route('/cuenta', methods=['DELETE'])
@jwt_required()
def eliminar_cuenta():
    usuario_id = get_jwt_identity()
    usuario = Usuario.query.get(usuario_id)
    
    if not usuario:
        return jsonify({"status": "error", "mensaje": "Usuario no encontrado"}), 404
        
    try:
        # 1. Borrar todas las ejecuciones (y sus archivos temporales) por el Restrict
        ejecuciones = Ejecucion.query.filter_by(id_usuario=usuario_id).all()
        for ejecucion in ejecuciones:
            # Borrar los archivos temporales asociados a esta ejecución
            archivos = TemporalArchivo.query.filter_by(id_ejecucion=ejecucion.id_ejecucion).all()
            for archivo in archivos:
                # Borrar el archivo físico si aún existe
                if archivo.ruta_servidor and os.path.exists(archivo.ruta_servidor):
                    try:
                        os.remove(archivo.ruta_servidor)
                    except:
                        pass
                # Borrar el registro del archivo
                db.session.delete(archivo)
            
            # Borrar la ejecución
            db.session.delete(ejecucion)

        # 2. Borrar alquileres y suscripciones por el Restrict
        Alquila.query.filter_by(id_usuario=usuario_id).delete()
        SuscripcionPlan.query.filter_by(id_usuario=usuario_id).delete()
        
        # 3. Finalmente, borramos el usuario. 
        # (USUARIO_ROL se borrará solo por el Cascade, y los PIPELINE se pondrán a NULL automáticamente)
        db.session.delete(usuario)
        
        db.session.commit()
        
        return jsonify({"status": "success", "mensaje": "Cuenta y datos asociados eliminados correctamente"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": f"Error al eliminar la cuenta: {str(e)}"}), 500
    
