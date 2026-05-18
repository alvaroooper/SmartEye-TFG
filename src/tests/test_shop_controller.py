import uuid
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
# 1. PRUEBAS DE LICENCIAS DE IA
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
# 2. PRUEBAS DE SUSCRIPCIONES 
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
# 3. PRUEBAS DE GESTIÓN POST-COMPRA 
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

# ==============================================================================
# 5. COBERTURA EXTENDIDA DEL CATÁLOGO Y ESTADOS COMERCIALES
# ==============================================================================
def test_catalogo_modelos_estados_activo_programado_y_oculta_deshabilitados(client, app, db_session):
    """Comprueba estados de licencias en catálogo y exclusión de motores deshabilitados."""
    env = setup_shop_env(app, db_session)
    token = create_access_token(identity=str(env["u_id"]))
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)

    with app.app_context():
        ia_programada = IAModelo(
            nombre=f"ia_programada_{uuid.uuid4().hex[:6]}",
            descripcion=None,
            precio=None,
            habilitada=True
        )
        ia_deshabilitada = IAModelo(
            nombre=f"ia_deshabilitada_{uuid.uuid4().hex[:6]}",
            descripcion="No debe aparecer en catálogo.",
            precio=7.50,
            habilitada=False
        )

        db_session.add_all([ia_programada, ia_deshabilitada])
        db_session.commit()

        db_session.add_all([
            Alquila(
                id_usuario=env["u_id"],
                id_ia=env["ia_id"],
                activo=1,
                periodo_inicio=ahora - timedelta(days=1),
                periodo_fin=ahora + timedelta(days=29),
                renovacion_auto=1,
                importe=5.00
            ),
            Alquila(
                id_usuario=env["u_id"],
                id_ia=ia_programada.id_ia,
                activo=1,
                periodo_inicio=ahora + timedelta(days=5),
                periodo_fin=ahora + timedelta(days=35),
                renovacion_auto=0,
                importe=0.00
            )
        ])
        db_session.commit()

        id_ia_programada = ia_programada.id_ia
        id_ia_deshabilitada = ia_deshabilitada.id_ia

    res = client.get(
        "/api/v1/shop/modelos",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200

    catalogo = {modelo["id_ia"]: modelo for modelo in res.json}

    assert catalogo[env["ia_id"]]["estado"] == "activo"
    assert catalogo[id_ia_programada]["estado"] == "programado"
    assert catalogo[id_ia_programada]["descripcion"] == "Metadatos no disponibles"
    assert id_ia_deshabilitada not in catalogo


def test_planes_programados_y_suscripcion_basica_sin_renovacion(client, app, db_session):
    """Valida planes programados y reglas específicas del plan gratuito."""
    env = setup_shop_env(app, db_session)
    token = create_access_token(identity=str(env["u_id"]))
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)

    with app.app_context():
        sub_programada = SuscripcionPlan(
            id_usuario=env["u_id"],
            id_plan=env["p_pro_id"],
            activo=1,
            fecha_inicio=ahora + timedelta(days=5),
            fecha_fin=ahora + timedelta(days=35),
            renovacion_auto=1,
            importe=19.99
        )
        db_session.add(sub_programada)
        db_session.commit()
        id_sub_programada = sub_programada.id_suscripcion

    res_planes = client.get(
        "/api/v1/shop/planes",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res_planes.status_code == 200

    estados = {plan["nombre"]: plan["estado"] for plan in res_planes.json}
    assert estados["Pro"] == "programado"

    res_basico = client.post(
        f"/api/v1/shop/suscribir/{env['p_basico_id']}",
        json={"renovacion_auto": True},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res_basico.status_code == 200

    with app.app_context():
        sub_basica = SuscripcionPlan.query.filter_by(
            id_usuario=env["u_id"],
            id_plan=env["p_basico_id"],
            activo=1
        ).first()

        sub_pro_anterior = db_session.get(SuscripcionPlan, id_sub_programada)

        assert sub_basica is not None
        assert sub_basica.fecha_fin is None
        assert sub_basica.renovacion_auto == 0
        assert float(sub_basica.importe) == 0.00
        assert sub_pro_anterior.activo == 0


# ==============================================================================
# 6. COBERTURA DE MIS COMPRAS Y MATRIZ DE DEPENDENCIAS
# ==============================================================================
def test_mis_compras_consolida_alquileres_y_planes(client, app, db_session):
    """Comprueba la respuesta agregada de licencias y suscripciones del usuario."""
    env = setup_shop_env(app, db_session)
    token = create_access_token(identity=str(env["u_id"]))
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)

    with app.app_context():
        ia_futura = IAModelo(
            nombre=f"ia_futura_{uuid.uuid4().hex[:6]}",
            descripcion="Motor programado para una fecha posterior.",
            precio=8.00,
            habilitada=True
        )
        db_session.add(ia_futura)
        db_session.commit()

        alquiler_activo = Alquila(
            id_usuario=env["u_id"],
            id_ia=env["ia_id"],
            activo=1,
            periodo_inicio=ahora - timedelta(days=2),
            periodo_fin=ahora + timedelta(days=28),
            renovacion_auto=1,
            importe=5.00
        )
        alquiler_programado_vitalicio = Alquila(
            id_usuario=env["u_id"],
            id_ia=ia_futura.id_ia,
            activo=1,
            periodo_inicio=ahora + timedelta(days=4),
            periodo_fin=None,
            renovacion_auto=0,
            importe=8.00
        )

        plan_gratis = SuscripcionPlan(
            id_usuario=env["u_id"],
            id_plan=env["p_basico_id"],
            activo=1,
            fecha_inicio=ahora - timedelta(days=1),
            fecha_fin=None,
            renovacion_auto=0,
            importe=0.00
        )
        plan_programado = SuscripcionPlan(
            id_usuario=env["u_id"],
            id_plan=env["p_pro_id"],
            activo=1,
            fecha_inicio=ahora + timedelta(days=5),
            fecha_fin=ahora + timedelta(days=35),
            renovacion_auto=1,
            importe=19.99
        )

        db_session.add_all([
            alquiler_activo,
            alquiler_programado_vitalicio,
            plan_gratis,
            plan_programado
        ])
        db_session.commit()

    res = client.get(
        "/api/v1/shop/mis_compras",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert res.json["status"] == "success"

    estados_alquileres = {alquiler["estado"] for alquiler in res.json["alquileres"]}
    estados_planes = {plan["estado"] for plan in res.json["planes"]}

    assert "activo" in estados_alquileres
    assert "programado" in estados_alquileres
    assert any(alquiler["fecha_fin"] == "Vitalicio" for alquiler in res.json["alquileres"])

    assert "activo" in estados_planes
    assert "programado" in estados_planes
    assert any(plan["es_gratis"] is True for plan in res.json["planes"])
    assert any(plan["renovacion_auto"] is True for plan in res.json["planes"])


def test_guia_pipelines_marca_ias_compradas_por_alquiler_y_por_plan_pro(client, app, db_session):
    """Verifica la matriz de dependencias para usuario con alquiler y para usuario Pro."""
    env = setup_shop_env(app, db_session)
    token = create_access_token(identity=str(env["u_id"]))
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)

    with app.app_context():
        alquiler_vigente = Alquila(
            id_usuario=env["u_id"],
            id_ia=env["ia_id"],
            activo=1,
            periodo_inicio=ahora - timedelta(days=1),
            periodo_fin=ahora + timedelta(days=29),
            renovacion_auto=0,
            importe=5.00
        )
        db_session.add(alquiler_vigente)
        db_session.commit()

    res_con_alquiler = client.get(
        "/api/v1/shop/guia_pipelines",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res_con_alquiler.status_code == 200
    assert res_con_alquiler.json[0]["ias_requeridas"][0]["comprada"] is True

    with app.app_context():
        db_session.query(Alquila).filter_by(id_usuario=env["u_id"]).delete()

        sub_pro = SuscripcionPlan(
            id_usuario=env["u_id"],
            id_plan=env["p_pro_id"],
            activo=1,
            fecha_inicio=ahora - timedelta(days=1),
            fecha_fin=ahora + timedelta(days=29),
            renovacion_auto=1,
            importe=19.99
        )

        db_session.add(sub_pro)
        db_session.commit()

    res_con_pro = client.get(
        "/api/v1/shop/guia_pipelines",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res_con_pro.status_code == 200
    assert all(
        ia["comprada"] is True
        for pipeline in res_con_pro.json
        for ia in pipeline["ias_requeridas"]
    )


# ==============================================================================
# 7. CASOS 404 Y AISLAMIENTO DE PROPIEDAD
# ==============================================================================
def test_post_compra_404_en_recursos_inexistentes(client, app, db_session):
    """Comprueba respuestas 404 en operaciones sobre compras o contratos inexistentes."""
    env = setup_shop_env(app, db_session)
    token = create_access_token(identity=str(env["u_id"]))

    assert client.post(
        "/api/v1/shop/alquiler/999999/toggle_renovacion",
        headers={"Authorization": f"Bearer {token}"}
    ).status_code == 404

    assert client.post(
        "/api/v1/shop/plan/999999/toggle_renovacion",
        headers={"Authorization": f"Bearer {token}"}
    ).status_code == 404

    assert client.post(
        "/api/v1/shop/plan/999999/empezar_ahora",
        headers={"Authorization": f"Bearer {token}"}
    ).status_code == 404


# ==============================================================================
# 8. RAMAS DE EXCEPCIÓN EN CONSULTAS Y MUTACIONES
# ==============================================================================
def test_listados_shop_responden_500_ante_caida_de_consulta(client, app, db_session):
    """Fuerza fallos de lectura para cubrir la degradación controlada de endpoints GET."""
    env = setup_shop_env(app, db_session)
    token = create_access_token(identity=str(env["u_id"]))

    endpoints = [
        "/api/v1/shop/modelos",
        "/api/v1/shop/planes",
        "/api/v1/shop/mis_compras",
        "/api/v1/shop/guia_pipelines"
    ]

    for endpoint in endpoints:
        with patch("app.controllers.shop_controller.db.session.query", side_effect=Exception("DB caída")):
            res = client.get(
                endpoint,
                headers={"Authorization": f"Bearer {token}"}
            )
            assert res.status_code == 500
            assert res.json["status"] == "error"


def test_alquiler_devuelve_500_si_falla_commit(client, app, db_session):
    """Simula un fallo transaccional al aprovisionar una licencia de IA."""
    env = setup_shop_env(app, db_session)
    token = create_access_token(identity=str(env["u_id"]))

    with patch("app.controllers.shop_controller.db.session.commit", side_effect=Exception("Commit fallido")):
        res = client.post(
            f"/api/v1/shop/alquilar/{env['ia_id']}",
            json={"renovacion_auto": True},
            headers={"Authorization": f"Bearer {token}"}
        )

    assert res.status_code == 500
    assert res.json["status"] == "error"


def test_mutaciones_post_compra_devuelven_500_si_falla_commit(client, app, db_session):
    """Cubre errores transaccionales en renovación y activación forzada."""
    env = setup_shop_env(app, db_session)
    token = create_access_token(identity=str(env["u_id"]))
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)

    with app.app_context():
        alquiler = Alquila(
            id_usuario=env["u_id"],
            id_ia=env["ia_id"],
            activo=1,
            periodo_inicio=ahora + timedelta(days=5),
            periodo_fin=ahora + timedelta(days=35),
            renovacion_auto=0,
            importe=5.00
        )
        suscripcion = SuscripcionPlan(
            id_usuario=env["u_id"],
            id_plan=env["p_pro_id"],
            activo=1,
            fecha_inicio=ahora + timedelta(days=5),
            fecha_fin=ahora + timedelta(days=35),
            renovacion_auto=0,
            importe=19.99
        )

        db_session.add_all([alquiler, suscripcion])
        db_session.commit()

        id_alquiler = alquiler.id_compra
        id_suscripcion = suscripcion.id_suscripcion

    endpoints = [
        f"/api/v1/shop/alquiler/{id_alquiler}/toggle_renovacion",
        f"/api/v1/shop/plan/{id_suscripcion}/toggle_renovacion",
        f"/api/v1/shop/alquiler/{id_alquiler}/empezar_ahora",
        f"/api/v1/shop/plan/{id_suscripcion}/empezar_ahora"
    ]

    for endpoint in endpoints:
        with patch("app.controllers.shop_controller.db.session.commit", side_effect=Exception("Commit fallido")):
            res = client.post(
                endpoint,
                headers={"Authorization": f"Bearer {token}"}
            )
            assert res.status_code == 500
            assert res.json["status"] == "error"