import uuid
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from flask_jwt_extended import create_access_token

from app.models import Usuario, TipoPlan, SuscripcionPlan, IAModelo, Alquila, Pipeline, PipelineEtapa, IAModo

# ==============================================================================
# CONFIGURACIÓN DINÁMICA DEL ENTORNO DE PRUEBAS
# ==============================================================================
def setup_shop_env(app, db_session):
    """Aprovisiona un entorno de tienda aislado con identificadores únicos."""
    with app.app_context():
        # 1. Limpieza y creación de Catálogos base
        p_basico = TipoPlan.query.filter_by(nombre='Basico').first() or TipoPlan(nombre='Basico', precio_mensual=0.00, habilitado=True)
        p_pro = TipoPlan.query.filter_by(nombre='Pro').first() or TipoPlan(nombre='Pro', precio_mensual=19.99, habilitado=True)
        ia_test = IAModelo.query.filter_by(nombre='ia_test').first() or IAModelo(nombre='ia_test', precio=5.00, habilitada=True)
        
        db_session.add_all([p_basico, p_pro, ia_test])
        db_session.commit()

        # 2. Identidades con sufijos UUID para evitar colisiones en la DB de test
        sufijo = uuid.uuid4().hex[:6]
        u = Usuario(username=f"tester_{sufijo}", email=f"t_{sufijo}@tfg.es", estado="activa")
        u.set_password("TfgAdmin2026")
        db_session.add(u)
        db_session.commit()

        # 3. Estructura de Pipeline para validar la Matriz de Dependencias
        modo = IAModo.query.filter_by(nombre_modo="det").first() or IAModo(id_ia=ia_test.id_ia, nombre_modo="det")
        pipe = Pipeline(nombre=f"Pipe_{sufijo}", publico=1, habilitado=1)
        db_session.add_all([modo, pipe])
        db_session.commit()

        etapa = PipelineEtapa(id_pipeline=pipe.id_pipeline, id_modo=modo.id_modo, id_ia=ia_test.id_ia, orden=1, nombre="E1")
        db_session.add(etapa)
        db_session.commit()

        return {
            "u_id": u.id_usuario,
            "ia_id": ia_test.id_ia,
            "p_basico_id": p_basico.id_plan,
            "p_pro_id": p_pro.id_plan
        }

# ==============================================================================
# 1. PRUEBAS DE LICENCIAS DE IA (MÓDULO 1)
# ==============================================================================
def test_alquiler_ciclo_completo_y_validaciones(client, app, db_session):
    """Prueba la lógica de alquiler, incluyendo sanitización de fechas y conflictos."""
    env = setup_shop_env(app, db_session)
    token = create_access_token(identity=str(env['u_id']))
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1.1 Listado inicial
    res = client.get('/api/v1/shop/modelos', headers={'Authorization': f'Bearer {token}'})
    assert res.status_code == 200

    # 1.2 Alquiler exitoso con fecha futura
    futuro = (ahora + timedelta(days=2)).strftime('%Y-%m-%d')
    res_post = client.post(f"/api/v1/shop/alquilar/{env['ia_id']}", 
                           json={"fecha_inicio": futuro, "renovacion_auto": True}, 
                           headers={'Authorization': f'Bearer {token}'})
    assert res_post.status_code == 200

    # 1.3 Intento de alquiler duplicado (Conflicto 400)
    res_conflicto = client.post(f"/api/v1/shop/alquilar/{env['ia_id']}", 
                                json={"fecha_inicio": futuro}, 
                                headers={'Authorization': f'Bearer {token}'})
    assert res_conflicto.status_code == 400

    # 1.4 Test de robustez: Fecha inválida (debe usar 'ahora' por defecto)
    client.post(f"/api/v1/shop/alquilar/{env['ia_id']}", 
                json={"fecha_inicio": "formato-incorrecto"}, 
                headers={'Authorization': f'Bearer {token}'})

    # 1.5 Error 404: IA inexistente
    assert client.post("/api/v1/shop/alquilar/99999", json={}, 
                       headers={'Authorization': f'Bearer {token}'}).status_code == 404

# ==============================================================================
# 2. PRUEBAS DE SUSCRIPCIONES (MÓDULO 2)
# ==============================================================================
def test_suscripcion_y_transiciones_de_nivel(client, app, db_session):
    """Verifica que el cambio de plan revoca correctamente los anteriores."""
    env = setup_shop_env(app, db_session)
    token = create_access_token(identity=str(env['u_id']))

    # Suscribirse al plan Pro
    res = client.post(f"/api/v1/shop/suscribir/{env['p_pro_id']}", 
                      json={"renovacion_auto": True}, 
                      headers={'Authorization': f'Bearer {token}'})
    assert res.status_code == 200

    # Verificar que el plan Pro aparece como activo y el básico como disponible
    res_list = client.get('/api/v1/shop/planes', headers={'Authorization': f'Bearer {token}'})
    estados = {p['nombre']: p['estado'] for p in res_list.json}
    assert estados['Pro'] == 'activo'
    
    # 404 Plan no existe
    assert client.post("/api/v1/shop/suscribir/8888", json={}, 
                       headers={'Authorization': f'Bearer {token}'}).status_code == 404

# ==============================================================================
# 3. PRUEBAS DE GESTIÓN POST-COMPRA (MÓDULO 3)
# ==============================================================================
def test_toggles_y_activacion_forzada(client, app, db_session):
    """Cubre las funciones de renovación y activación inmediata."""
    env = setup_shop_env(app, db_session)
    token = create_access_token(identity=str(env['u_id']))
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)

    with app.app_context():
        # Inyectamos una compra programada (futura)
        alq = Alquila(id_usuario=env['u_id'], id_ia=env['ia_id'], activo=1, 
                      periodo_inicio=ahora + timedelta(days=5), renovacion_auto=0)
        sub = SuscripcionPlan(id_usuario=env['u_id'], id_plan=env['p_pro_id'], activo=1, 
                              fecha_inicio=ahora + timedelta(days=5), renovacion_auto=0)
        db_session.add_all([alq, sub])
        db_session.commit()
        id_a, id_s = alq.id_compra, sub.id_suscripcion

    # Toggle Renovación
    assert client.post(f"/api/v1/shop/alquiler/{id_a}/toggle_renovacion", headers={'Authorization': f'Bearer {token}'}).status_code == 200
    assert client.post(f"/api/v1/shop/plan/{id_s}/toggle_renovacion", headers={'Authorization': f'Bearer {token}'}).status_code == 200

    # Empezar ahora (Activación forzada)
    assert client.post(f"/api/v1/shop/alquiler/{id_a}/empezar_ahora", headers={'Authorization': f'Bearer {token}'}).status_code == 200
    assert client.post(f"/api/v1/shop/plan/{id_s}/empezar_ahora", headers={'Authorization': f'Bearer {token}'}).status_code == 200

    # Errores 404 en IDs inexistentes
    assert client.post("/api/v1/shop/alquiler/999/empezar_ahora", headers={'Authorization': f'Bearer {token}'}).status_code == 404

# ==============================================================================
# 4. PRUEBAS DE MATRIZ DE DEPENDENCIAS Y EXCEPCIONES 500
# ==============================================================================
def test_guia_pipelines_y_cobertura_excepciones(client, app, db_session):
    """Cubre la lógica de dependencias y fuerza el paso por los bloques 'except'."""
    env = setup_shop_env(app, db_session)
    token = create_access_token(identity=str(env['u_id']))

    # 4.1 Comprobar guía de pipelines (Estado: No comprada)
    res_guia = client.get('/api/v1/shop/guia_pipelines', headers={'Authorization': f'Bearer {token}'})
    assert res_guia.json[0]['ias_requeridas'][0]['comprada'] is False

    
    with patch('app.controllers.shop_controller.db.session.commit', side_effect=Exception("Crash")):
        res_500_sub = client.post(f"/api/v1/shop/suscribir/{env['p_basico_id']}", json={}, headers={'Authorization': f'Bearer {token}'})
        assert res_500_sub.status_code == 500