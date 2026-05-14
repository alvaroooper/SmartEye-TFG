from unittest.mock import patch
from app.controllers.auth_controller import validar_password_segura
from app.models import Usuario, Rol, SuscripcionPlan, TipoPlan
from flask_jwt_extended import create_access_token

# ==============================================================================
# HELPERS DE CONFIGURACIÓN DE ENTORNO
# ==============================================================================
def asegurar_catalogos(db_session):
    """Garantiza la persistencia de entidades maestras (Catálogos) para el entorno transaccional."""
    if not Rol.query.filter_by(nombre='usuario').first():
        db_session.add(Rol(nombre='usuario'))
    if not Rol.query.filter_by(nombre='admin').first():
        db_session.add(Rol(nombre='admin'))
    if not TipoPlan.query.filter_by(nombre='Basico').first():
        db_session.add(TipoPlan(nombre='Basico', precio_mensual=0.00))
    db_session.commit()

# ==============================================================================
# 1. EVALUACIÓN DE POLÍTICAS DE SEGURIDAD (Criptografía y Validaciones)
# ==============================================================================
def test_validar_password_segura():
    """Comprueba las reglas mínimas de seguridad de la contraseña."""
    assert validar_password_segura("TfgAdmin2026")[0] is True
    assert validar_password_segura("corta1A")[0] is False  # Longitud insuficiente
    assert validar_password_segura("solominusculas1")[0] is False  # Ausencia de mayúsculas
    assert validar_password_segura("SOLOMAYUSCULAS1")[0] is False  # Ausencia de minúsculas
    assert validar_password_segura("SinNumerosNiSignos")[0] is False  # Ausencia de numéricos

# ==============================================================================
# 2. APROVISIONAMIENTO DE IDENTIDADES (/register)
# ==============================================================================
def test_registro_exitoso(client, app, db_session):
    """Flujo nominal: Alta de usuario, asignación de roles y aprovisionamiento comercial."""
    with app.app_context():
        asegurar_catalogos(db_session)
        
    payload = {
        "username": "nuevo_usuario",
        "email": "nuevo@tfg.es",
        "password": "PasswordFuerte123",
        "nombre_visible": "Nuevo Tester"
    }
    response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 201
    assert 'token' in response.json
    
    with app.app_context():
        u = Usuario.query.filter_by(email="nuevo@tfg.es").first()
        assert u is not None
        assert any(r.nombre == 'usuario' for r in u.roles)
        sub = SuscripcionPlan.query.filter_by(id_usuario=u.id_usuario).first()
        assert sub is not None

def test_registro_email_duplicado(client, app, db_session):
    """Prevención de colisiones: Control de unicidad paramétrica."""
    with app.app_context():
        u = Usuario(username="existente", email="existe@tfg.es", estado="activa")
        u.set_password("Admin123")
        db_session.add(u)
        db_session.commit()
    
    payload = {"username": "otro", "email": "existe@tfg.es", "password": "PasswordFuerte123"}
    response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 400
    assert "ya consta" in response.json['mensaje']

def test_registro_password_debil(client):
    """Intercepción en Capa 1: Rechazo de payload por incumplimiento de política criptográfica."""
    payload = {"username": "weak", "email": "weak@tfg.es", "password": "corta"}
    response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 400

def test_registro_excepcion_500(client, app, db_session):
    """Prueba el bloque 'except' forzando un error de commit mediante Mocking."""
    payload = {"username": "crash_test", "email": "crash@tfg.es", "password": "Password123"}
    with patch('app.controllers.auth_controller.db.session.commit', side_effect=Exception("Database Down")):
        res = client.post('/api/v1/auth/register', json=payload)
        assert res.status_code == 500

def test_registro_payload_incompleto_falla_con_html(client):
    """
    Inyección de un payload incompleto (sin el campo 'password').
    El test espera que la API valide la entrada y devuelva un 400 Bad Request en JSON.
    """
    payload_incompleto = {
        "username": "hacker_sin_pass",
        "email": "hacker@tfg.es"
    }
    
    response = client.post('/api/v1/auth/register', json=payload_incompleto)

    assert response.status_code == 400, f"Se esperaba 400, pero la API devolvió {response.status_code}"
    assert response.is_json is True, "La API rompió el contrato y no devolvió un JSON"
    assert "status" in response.json

# ==============================================================================
# 3. RESOLUCIÓN DE SESIONES Y AUTENTICACIÓN (/login)
# ==============================================================================
def test_login_exito_y_fallos(client, app, db_session):
    """Auditoría del motor de autenticación: evaluación de vectores duales y control de estados lógicos."""
    with app.app_context():
        u_activo = Usuario(username="activo", email="a@tfg.es", estado="activa")
        u_activo.set_password("Pass1234")
        u_banned = Usuario(username="banned", email="b@tfg.es", estado="suspendida")
        u_banned.set_password("Pass1234")
        db_session.add_all([u_activo, u_banned])
        db_session.commit()

    # Credenciales inválidas
    assert client.post('/api/v1/auth/login', json={"identificador": "a@tfg.es", "password": "Mal"}).status_code == 401
    assert client.post('/api/v1/auth/login', json={"identificador": "fantasma", "password": "Pass1234"}).status_code == 401
    
    # Restricción de acceso a identidad bloqueada
    assert client.post('/api/v1/auth/login', json={"identificador": "b@tfg.es", "password": "Pass1234"}).status_code == 403
    
    # Resolución exitosa (Vector Username)
    assert client.post('/api/v1/auth/login', json={"identificador": "activo", "password": "Pass1234"}).status_code == 200
    # Resolución exitosa (Vector Email)
    assert client.post('/api/v1/auth/login', json={"identificador": "a@tfg.es", "password": "Pass1234"}).status_code == 200

# ==============================================================================
# 4. AUDITORÍA DE CATÁLOGO (GET /usuarios)
# ==============================================================================
def test_listar_usuarios_rbac(client, app, db_session):
    """Validación del modelo RBAC y mitigación de escalada de privilegios."""
    with app.app_context():
        u_admin = Usuario(username="ad_list", email="al@tfg.es")
        u_admin.set_password("Pass1234")
        u_user = Usuario(username="us_list", email="ul@tfg.es")
        u_user.set_password("Pass1234")
        db_session.add_all([u_admin, u_user])
        db_session.commit()
        
        token_admin = create_access_token(identity=str(u_admin.id_usuario), additional_claims={"roles": ["admin"]})
        token_user = create_access_token(identity=str(u_user.id_usuario), additional_claims={"roles": ["usuario"]})

    assert client.get('/api/v1/auth/usuarios', headers={'Authorization': f'Bearer {token_user}'}).status_code == 403
    res_admin = client.get('/api/v1/auth/usuarios', headers={'Authorization': f'Bearer {token_admin}'})
    assert res_admin.status_code == 200
    assert isinstance(res_admin.json, list)

# ==============================================================================
# 5. LECTURA DE METADATOS DE IDENTIDAD (GET /perfil)
# ==============================================================================
def test_obtener_perfil(client, app, db_session):
    """Resolución de contexto de sesión mediante JWT."""
    with app.app_context():
        u = Usuario(username="perfil", email="p@tfg.es", nombre_visible="Mi Perfil")
        u.set_password("Pass1234")
        db_session.add(u)
        db_session.commit()
        token = create_access_token(identity=str(u.id_usuario))

    res = client.get('/api/v1/auth/perfil', headers={'Authorization': f'Bearer {token}'})
    assert res.status_code == 200
    assert res.json['datos']['nombre_visible'] == "Mi Perfil"
    
    # Manejo de token huérfano (Registro eliminado físicamente)
    assert client.get('/api/v1/auth/perfil', headers={'Authorization': f'Bearer {create_access_token(identity="9999")}'}).status_code == 404

# ==============================================================================
# 6. MUTACIÓN DE ATRIBUTOS Y CREDENCIALES (PUT /perfil)
# ==============================================================================
def test_actualizar_perfil_flujos(client, app, db_session):
    """Cobertura de validaciones en actualización de hash y metadatos."""
    with app.app_context():
        u = Usuario(username="mut", email="m@tfg.es")
        u.set_password("OldPass123")
        db_session.add(u)
        db_session.commit()
        token = create_access_token(identity=str(u.id_usuario))

    # Mutación estándar
    assert client.put('/api/v1/auth/perfil', json={"nombre_visible": "Nuevo"}, headers={'Authorization': f'Bearer {token}'}).status_code == 200
    
    # Violaciones de seguridad detectadas
    assert client.put('/api/v1/auth/perfil', json={"password": "New"}, headers={'Authorization': f'Bearer {token}'}).status_code == 400
    assert client.put('/api/v1/auth/perfil', json={"password": "New", "old_password": "Fake"}, headers={'Authorization': f'Bearer {token}'}).status_code == 401
    assert client.put('/api/v1/auth/perfil', json={"password": "corta", "old_password": "OldPass123"}, headers={'Authorization': f'Bearer {token}'}).status_code == 400
    
    # Cambio autorizado
    assert client.put('/api/v1/auth/perfil', json={"password": "NewPass1234", "old_password": "OldPass123"}, headers={'Authorization': f'Bearer {token}'}).status_code == 200

def test_actualizar_perfil_excepcion(client, app, db_session):
    """Aislamiento del comportamiento ante una degradación de la capa de persistencia."""
    with app.app_context():
        u = Usuario(username="err_put", email="ep@tfg.es")
        u.set_password("Pass1234")
        db_session.add(u)
        db_session.commit()
        token = create_access_token(identity=str(u.id_usuario))
        
    # El mock intercepta únicamente la operación atómica
    with patch('app.controllers.auth_controller.db.session.commit', side_effect=Exception("Fallo inducido")):
        res = client.put('/api/v1/auth/perfil', json={"nombre_visible": "Fallo"}, headers={'Authorization': f'Bearer {token}'})
        assert res.status_code == 500

# ==============================================================================
# 7. POLÍTICAS DE RETENCIÓN DE DATOS (DELETE /cuenta)
# ==============================================================================
def test_eliminar_cuenta_cascada(client, app, db_session):
    """Validación del protocolo Soft-Delete y revocación en cascada para cumplimiento RGPD."""
    with app.app_context():
        asegurar_catalogos(db_session)
        u = Usuario(username="del_user", email="del@tfg.es", estado="activa")
        u.set_password("Pass1234")
        plan = TipoPlan.query.filter_by(nombre='Basico').first()
        db_session.add(u)
        db_session.commit()
        
        sub = SuscripcionPlan(id_usuario=u.id_usuario, id_plan=plan.id_plan, activo=1, renovacion_auto=1)
        db_session.add(sub)
        db_session.commit()
        
        user_id = u.id_usuario  # Prevención de DetachedInstanceError
        token = create_access_token(identity=str(user_id))

    assert client.delete('/api/v1/auth/cuenta', headers={'Authorization': f'Bearer {create_access_token(identity="999")}'}).status_code == 404
    assert client.delete('/api/v1/auth/cuenta', headers={'Authorization': f'Bearer {token}'}).status_code == 200
    
    with app.app_context():
        u_bd = db_session.get(Usuario, user_id)
        sub_bd = SuscripcionPlan.query.filter_by(id_usuario=user_id).first()
        assert u_bd.estado == 'borrada'
        assert sub_bd.activo == 0

def test_eliminar_cuenta_excepcion(client, app, db_session):
    """Inyección de excepción durante el proceso de baja del servicio."""
    with app.app_context():
        u = Usuario(username="del_err", email="de@tfg.es")
        u.set_password("Pass1234")
        db_session.add(u)
        db_session.commit()
        token = create_access_token(identity=str(u.id_usuario))
        
    with patch('app.controllers.auth_controller.db.session.commit', side_effect=Exception("Fallo transaccional inducido")):
        assert client.delete('/api/v1/auth/cuenta', headers={'Authorization': f'Bearer {token}'}).status_code == 500

# ==============================================================================
# 8. CONSOLA DE ADMINISTRACIÓN (POST /admin/cambiar_estado)
# ==============================================================================
def test_admin_cambiar_estado_flujos(client, app, db_session):
    """Validación del modelo de intervención de identidades (Bloqueo y Baja Forzosa)."""
    with app.app_context():
        u_admin = Usuario(username="ad_state", email="as@tfg.es")
        u_admin.set_password("Pass1234")
        u_target = Usuario(username="target", email="t@tfg.es", estado="activa")
        u_target.set_password("Pass1234")
        db_session.add_all([u_admin, u_target])
        db_session.commit()
        
        # Extracción de variables a primitivas para evitar DetachedInstanceError
        admin_id = u_admin.id_usuario
        target_id = u_target.id_usuario
        token_admin = create_access_token(identity=str(admin_id), additional_claims={"roles": ["admin"]})

    assert client.post('/api/v1/auth/admin/cambiar_estado/999', json={"estado": "suspendida"}, headers={'Authorization': f'Bearer {token_admin}'}).status_code == 404
    assert client.post(f'/api/v1/auth/admin/cambiar_estado/{admin_id}', json={"estado": "suspendida"}, headers={'Authorization': f'Bearer {token_admin}'}).status_code == 400
    
    res_susp = client.post(f'/api/v1/auth/admin/cambiar_estado/{target_id}', json={"estado": "suspendida"}, headers={'Authorization': f'Bearer {token_admin}'})
    assert res_susp.status_code == 200
    
    res_borr = client.post(f'/api/v1/auth/admin/cambiar_estado/{target_id}', json={"estado": "borrada"}, headers={'Authorization': f'Bearer {token_admin}'})
    assert res_borr.status_code == 200
    
    with app.app_context():
        u_verif = db_session.get(Usuario, target_id)
        assert u_verif.estado == 'borrada'
        assert u_verif.borrado_en is not None

def test_admin_cambiar_estado_excepcion(client, app, db_session):
    """Manejo de errores durante la mutación de estado administrativo."""
    with app.app_context():
        u_admin = Usuario(username="ad_err", email="ae@tfg.es")
        u_admin.set_password("Pass1234")
        u_target = Usuario(username="tar_err", email="te@tfg.es")
        u_target.set_password("Pass1234")
        db_session.add_all([u_admin, u_target])
        db_session.commit()
        
        target_id = u_target.id_usuario
        token = create_access_token(identity=str(u_admin.id_usuario), additional_claims={"roles": ["admin"]})
        
    with patch('app.controllers.auth_controller.db.session.commit', side_effect=Exception("Fallo inducido")):
        res = client.post(f'/api/v1/auth/admin/cambiar_estado/{target_id}', json={"estado": "suspendida"}, headers={'Authorization': f'Bearer {token}'})
        assert res.status_code == 500
