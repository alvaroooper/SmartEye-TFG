import os
import io
import json
import uuid
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, mock_open
from flask_jwt_extended import create_access_token

from app.models import (
    Usuario, Rol, TipoPlan, SuscripcionPlan, IAModelo, IAModo, Alquila,
    Pipeline, PipelineEtapa, Ejecucion, TemporalArchivo
)

# ==============================================================================
# FIXTURES Y HELPERS DE ENTORNO 
# ==============================================================================
def setup_pipeline_env(app, db_session):
    """Aprovisiona el entorno relacional base para auditoría de pipelines evitando IntegrityErrors."""
    with app.app_context():
        # 1. Catálogos Idempotentes (Recuperar si existen, crear si no)
        r_admin = Rol.query.filter_by(nombre='admin').first() or Rol(nombre='admin')
        r_user = Rol.query.filter_by(nombre='usuario').first() or Rol(nombre='usuario')
        
        plan_pro = TipoPlan.query.filter_by(nombre='Pro').first() or TipoPlan(nombre='Pro', precio_mensual=19.99)
        plan_basico = TipoPlan.query.filter_by(nombre='Basico').first() or TipoPlan(nombre='Basico', precio_mensual=0)
        
        ia_yolo = IAModelo.query.filter_by(nombre="yolo").first() or IAModelo(nombre="yolo", precio=10.0)
        ia_mp = IAModelo.query.filter_by(nombre="mediapipe").first() or IAModelo(nombre="mediapipe", precio=5.0)
        
        db_session.add_all([r_admin, r_user, plan_pro, plan_basico, ia_yolo, ia_mp])
        db_session.commit()
        
        # 2. Identidades Efímeras (Uso de UUID corto para evitar colisiones entre tests)
        sufijo = str(uuid.uuid4())[:6]
        
        u_admin = Usuario(username=f"adm_{sufijo}", email=f"a_{sufijo}@tfg.es", estado="activa")
        u_admin.set_password("Pass123")
        u_admin.roles.append(r_admin)
        
        u_pro = Usuario(username=f"pro_{sufijo}", email=f"p_{sufijo}@tfg.es", estado="activa")
        u_pro.set_password("Pass123")
        u_pro.roles.append(r_user)
        
        u_basic = Usuario(username=f"bas_{sufijo}", email=f"b_{sufijo}@tfg.es", estado="activa")
        u_basic.set_password("Pass123")
        u_basic.roles.append(r_user)
        
        db_session.add_all([u_admin, u_pro, u_basic])
        db_session.commit()
        
        # 3. Modelos, Pipelines y Suscripciones
        modo_det = IAModo.query.filter_by(nombre_modo="deteccion").first() or IAModo(id_ia=ia_yolo.id_ia, nombre_modo="deteccion", config_predeterminada="configs/dummy.json")
        modo_pose = IAModo.query.filter_by(nombre_modo="pose").first() or IAModo(id_ia=ia_mp.id_ia, nombre_modo="pose")
        
        sub_pro = SuscripcionPlan(id_usuario=u_pro.id_usuario, id_plan=plan_pro.id_plan, activo=1)
        sub_basic = SuscripcionPlan(id_usuario=u_basic.id_usuario, id_plan=plan_basico.id_plan, activo=1)
        
        p_pub = Pipeline(nombre=f"Pub_{sufijo}", publico=1)
        p_priv = Pipeline(nombre=f"Priv_{sufijo}", publico=0)
        db_session.add_all([modo_det, modo_pose, sub_pro, sub_basic, p_pub, p_priv])
        db_session.commit()
        
        # 4. Topología (Etapas)
        e1 = PipelineEtapa(id_pipeline=p_pub.id_pipeline, id_modo=modo_det.id_modo, id_ia=ia_yolo.id_ia, orden=1, nombre="E1")
        e2 = PipelineEtapa(id_pipeline=p_priv.id_pipeline, id_modo=modo_pose.id_modo, id_ia=ia_mp.id_ia, orden=1, nombre="E2")
        db_session.add_all([e1, e2])
        db_session.commit()
        
        return {
            "u_admin": u_admin.id_usuario,
            "u_pro": u_pro.id_usuario,
            "u_basic": u_basic.id_usuario,
            "ia_yolo": ia_yolo.id_ia,
            "ia_mp": ia_mp.id_ia,
            "p_pub": p_pub.id_pipeline,
            "p_priv": p_priv.id_pipeline
        }

# ==============================================================================
# 1. TAREAS ASÍNCRONAS DE MANTENIMIENTO (LIFECYCLE HOOKS)
# ==============================================================================
def test_mantenimiento_purga_y_anonimizacion(client, app, db_session):
    """Audita el recolector de basura y el cumplimiento RGPD."""
    env = setup_pipeline_env(app, db_session)
    ahora_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    
    with app.app_context():
        ej = Ejecucion(id_usuario=env['u_basic'], id_pipeline=env['p_pub'])
        db_session.add(ej)
        db_session.commit()
        arch_exp = TemporalArchivo(id_ejecucion=ej.id_ejecucion, expira_en=ahora_naive - timedelta(days=1), ruta_servidor="/tmp/fake.jpg")
        
        alq = Alquila(id_usuario=env['u_basic'], id_ia=env['ia_yolo'], periodo_fin=ahora_naive - timedelta(days=1), activo=1, renovacion_auto=1)
        sub = SuscripcionPlan.query.filter_by(id_usuario=env['u_pro']).first()
        sub.fecha_fin = ahora_naive - timedelta(days=1)
        sub.renovacion_auto = 1
        
        u_del = Usuario(username=f"del_{uuid.uuid4().hex[:6]}", email=f"d_{uuid.uuid4().hex[:6]}@tfg.es", estado="borrada", borrado_en=ahora_naive - timedelta(days=31))
        u_del.set_password("Pass")
        
        db_session.add_all([arch_exp, alq, u_del])
        db_session.commit()
        id_borrado = u_del.id_usuario

    token = create_access_token(identity=str(env['u_admin']), additional_claims={"roles": ["admin"]})
    client.get('/api/v1/listado', headers={'Authorization': f'Bearer {token}'})
    
    with app.app_context():
        assert TemporalArchivo.query.count() == 0
        assert Alquila.query.first().periodo_fin > ahora_naive
        assert SuscripcionPlan.query.filter_by(id_usuario=env['u_pro']).first().fecha_fin > ahora_naive
        
        u_anon = db_session.get(Usuario, id_borrado)
        assert u_anon.estado == 'anonimizado'

@patch('app.controllers.pipeline_controller.db.session.commit')
def test_mantenimiento_excepcion_silenciosa(mock_commit, client, app, db_session):
    """Garantiza que un fallo en el recolector de basura no interrumpe el servicio principal."""
    env = setup_pipeline_env(app, db_session)
    mock_commit.side_effect = Exception("Fallo inducido en GC")
    token = create_access_token(identity=str(env['u_admin']), additional_claims={"roles": ["admin"]})
    assert client.get('/api/v1/listado', headers={'Authorization': f'Bearer {token}'}).status_code == 200

# ==============================================================================
# 2. RESOLUCIÓN DE DEPENDENCIAS (CATÁLOGO Y CONFIGURACIONES)
# ==============================================================================
def test_listar_pipelines_rbac(client, app, db_session):
    """Verifica el filtrado de flujos según nivel de suscripción y activos contratados."""
    env = setup_pipeline_env(app, db_session)
    t_admin = create_access_token(identity=str(env['u_admin']), additional_claims={"roles": ["admin"]})
    t_pro = create_access_token(identity=str(env['u_pro']), additional_claims={"roles": ["usuario"]})
    t_basic = create_access_token(identity=str(env['u_basic']), additional_claims={"roles": ["usuario"]})
    
    assert len(client.get('/api/v1/listado', headers={'Authorization': f'Bearer {t_admin}'}).json) == 2
    assert len(client.get('/api/v1/listado', headers={'Authorization': f'Bearer {t_pro}'}).json) == 1
    assert len(client.get('/api/v1/listado', headers={'Authorization': f'Bearer {t_basic}'}).json) == 0
    
    with app.app_context():
        db_session.add(Alquila(id_usuario=env['u_basic'], id_ia=env['ia_yolo'], activo=1))
        db_session.commit()
    assert len(client.get('/api/v1/listado', headers={'Authorization': f'Bearer {t_basic}'}).json) == 1

def test_detalles_completos_admin(client, app, db_session):
    """Auditoría de introspección técnica de la consola administrativa."""
    env = setup_pipeline_env(app, db_session)
    t_admin = create_access_token(identity=str(env['u_admin']), additional_claims={"roles": ["admin"]})
    t_user = create_access_token(identity=str(env['u_pro']), additional_claims={"roles": ["usuario"]})
    
    assert client.get('/api/v1/detalles_completos', headers={'Authorization': f'Bearer {t_user}'}).status_code == 403
    res = client.get('/api/v1/detalles_completos', headers={'Authorization': f'Bearer {t_admin}'})
    assert res.status_code == 200
    assert len(res.json) == 2

@patch('os.path.exists', return_value=True)
@patch('builtins.open', new_callable=mock_open, read_data='{"conf": 0.5}')
def test_obtener_configuracion_completa(mock_file, mock_exists, client, app, db_session):
    """Ensamblado de esquemas JSON para configuración predeterminada de etapas."""
    env = setup_pipeline_env(app, db_session)
    t_user = create_access_token(identity=str(env['u_pro']), additional_claims={"roles": ["usuario"]})
    res = client.get(f"/api/v1/configuracion_pipeline/{env['p_pub']}", headers={'Authorization': f'Bearer {t_user}'})
    assert res.status_code == 200
    assert res.json["etapa_1"]["conf"] == 0.5

# ==============================================================================
# 3. MOTOR CENTRAL: ORQUESTACIÓN Y VULNERABILIDADES 
# ==============================================================================
def test_analizar_imagen_validacion_inputs(client, app, db_session):
    """Rechazo de payloads malformados en capa de controlador."""
    env = setup_pipeline_env(app, db_session)
    t_user = create_access_token(identity=str(env['u_pro']), additional_claims={"roles": ["usuario"]})
    
    assert client.post('/api/v1/analizar', headers={'Authorization': f'Bearer {t_user}'}).status_code == 400
    data_bad_ext = {'id_pipeline': env['p_pub'], 'imagen': (io.BytesIO(b"dummy"), 'script.py')}
    assert client.post('/api/v1/analizar', data=data_bad_ext, content_type='multipart/form-data', headers={'Authorization': f'Bearer {t_user}'}).status_code == 400

def test_analizar_imagen_json_invalido(client, app, db_session):
    """
    Exige que el controlador valide el JSON de configuración.
    Si el código no captura el JSONDecodeError, lanzará un 500 y este test FALLARÁ.
    Exigimos un 400 Bad Request.
    """
    env = setup_pipeline_env(app, db_session)
    t_user = create_access_token(identity=str(env['u_pro']), additional_claims={"roles": ["usuario"]})
    
    data_mal = {
        'id_pipeline': str(env['p_pub']),
        'config_personalizada': '{ "conf": 0.5, }', # JSON Inválido (coma sobrante)
        'imagen': (io.BytesIO(b"dummy"), 'test.jpg')
    }
    
    res = client.post('/api/v1/analizar', data=data_mal, content_type='multipart/form-data', headers={'Authorization': f'Bearer {t_user}'})

    assert res.status_code == 400
    assert "inválido" in res.json['mensaje'].lower()

@patch('app.controllers.pipeline_controller.PipelineRunner.ejecutar_pipeline')
def test_analizar_imagen_exito_flujo_completo(mock_runner, client, app, db_session):
    """Comprueba que una imagen válida ejecuta el pipeline y devuelve tokens de salida."""
    env = setup_pipeline_env(app, db_session)
    t_user = create_access_token(identity=str(env['u_pro']), additional_claims={"roles": ["usuario"]})
    
    mock_runner.return_value = (
        ['/tmp/dummy.jpg'], 
        [{"etapa": 1, "nombre_etapa": "Test", "ia": "yolo", "modo": "deteccion", "imagenes": ["out.jpg"], "datos": []}]
    )
    data = {'id_pipeline': env['p_pub'], 'config_personalizada': '{"etapa_1": {"conf": 0.8}}', 'imagen': (io.BytesIO(b"bytes"), 'test.jpg')}
    res = client.post('/api/v1/analizar', data=data, content_type='multipart/form-data', headers={'Authorization': f'Bearer {t_user}'})
    
    assert res.status_code == 200
    assert len(res.json['resultados_etapas'][0]['imagenes'][0]) > 20 

# ==============================================================================
# 4. GESTIÓN DE ARTEFACTOS Y TELEMETRÍA (/outputs, /historial, /archivos)
# ==============================================================================
@patch('app.controllers.pipeline_controller.send_file')
@patch('os.path.exists')
def test_serve_output_resolucion_segura(mock_exists, mock_send_file, client, app, db_session):
    """Validación de entrega de activos ofuscados (Token Resolution) y TTL."""
    env = setup_pipeline_env(app, db_session)
    ahora_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    with app.app_context():
        ej = Ejecucion(id_usuario=env['u_pro'], id_pipeline=env['p_pub'])
        db_session.add(ej)
        db_session.commit()
        db_session.add(TemporalArchivo(id_ejecucion=ej.id_ejecucion, token_descarga="T_OK", expira_en=ahora_naive + timedelta(days=1), ruta_servidor="/tmp/ok.jpg"))
        db_session.add(TemporalArchivo(id_ejecucion=ej.id_ejecucion, token_descarga="T_EXP", expira_en=ahora_naive - timedelta(days=1), ruta_servidor="/tmp/exp.jpg"))
        db_session.commit()

    # Configuración del Mock: Si le preguntan por /tmp/ok.jpg, decimos que SÍ existe. Para /tmp/exp.jpg, da igual porque caduca antes por TTL.
    mock_exists.side_effect = lambda path: True if path == "/tmp/ok.jpg" else False

    assert client.get('/api/v1/outputs/T_EXP').status_code == 404
    mock_send_file.return_value = "File"
    assert client.get('/api/v1/outputs/T_OK').status_code == 200

def test_serve_output_archivo_fisico_borrado(client, app, db_session):
    """
    Simulación de escenario real: Archivo registrado en DB pero físicamente purgado (Ej. GC del almacenamiento). Validación de manejo de excepciones y respuesta 404.
    """
    env = setup_pipeline_env(app, db_session)
    with app.app_context():
        ej = Ejecucion(id_usuario=env['u_pro'], id_pipeline=env['p_pub'])
        db_session.add(ej)
        db_session.commit()
        db_session.add(TemporalArchivo(id_ejecucion=ej.id_ejecucion, token_descarga="FANTASMA", expira_en=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1), ruta_servidor="/ruta/fake.jpg"))
        db_session.commit()
        
    assert client.get('/api/v1/outputs/FANTASMA').status_code == 404

def test_historial_y_archivos_ejecucion(client, app, db_session):
    """Reconstrucción del árbol de ejecución y validación de propiedad (Data Isolation)."""
    env = setup_pipeline_env(app, db_session)
    t_pro = create_access_token(identity=str(env['u_pro']), additional_claims={"roles": ["usuario"]})
    t_basic = create_access_token(identity=str(env['u_basic']), additional_claims={"roles": ["usuario"]})
    
    with app.app_context():
        ej = Ejecucion(id_usuario=env['u_pro'], id_pipeline=env['p_pub'], estado="completado")
        db_session.add(ej)
        db_session.commit()
        id_ej = ej.id_ejecucion
        db_session.add(TemporalArchivo(id_ejecucion=id_ej, tipo="imagen_original", token_descarga="IMG_O", ruta_servidor="/tmp/ok.jpg", expira_en=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)))
        db_session.commit()

    assert client.get('/api/v1/historial', headers={'Authorization': f'Bearer {t_pro}'}).status_code == 200
    assert client.get(f'/api/v1/ejecucion/{id_ej}/archivos', headers={'Authorization': f'Bearer {t_basic}'}).status_code == 403
    assert client.get(f'/api/v1/ejecucion/{id_ej}/archivos', headers={'Authorization': f'Bearer {t_pro}'}).status_code == 200

# ==============================================================================
# 5. SIMULACIÓN DE EXCEPCIONES GLOBALES EN CONTROLADORES
# ==============================================================================
@patch('app.controllers.pipeline_controller.PipelineEtapa.query')
@patch('app.controllers.pipeline_controller.Pipeline.query')
def test_excepciones_globales_bd(mock_query_pipeline, mock_query_etapa, client, app, db_session):
    """Forzado de excepciones SQLAlchemy para asegurar cobertura de bloques except 500."""
    env = setup_pipeline_env(app, db_session)
    t_admin = create_access_token(identity=str(env['u_admin']), additional_claims={"roles": ["admin"]})
    
    mock_query_pipeline.filter_by.side_effect = Exception("DB Caída")
    mock_query_pipeline.all.side_effect = Exception("DB Caída")
    mock_query_etapa.filter_by.side_effect = Exception("DB Caída")

    assert client.get('/api/v1/listado', headers={'Authorization': f'Bearer {t_admin}'}).status_code == 500
    assert client.get('/api/v1/detalles_completos', headers={'Authorization': f'Bearer {t_admin}'}).status_code == 500
    assert client.get(f"/api/v1/configuracion_pipeline/{env['p_pub']}", headers={'Authorization': f'Bearer {t_admin}'}).status_code == 500


# ==============================================================================
# 6. CONSOLA ADMINISTRATIVA DE PIPELINES
# ==============================================================================
def test_admin_catalogo_ia_rbac_y_contrato_respuesta(client, app, db_session):
    """Verifica que el catálogo técnico solo sea accesible por administradores."""
    env = setup_pipeline_env(app, db_session)

    t_admin = create_access_token(
        identity=str(env["u_admin"]),
        additional_claims={"roles": ["admin"]}
    )
    t_user = create_access_token(
        identity=str(env["u_pro"]),
        additional_claims={"roles": ["usuario"]}
    )

    res_user = client.get(
        "/api/v1/admin/catalogo_ia",
        headers={"Authorization": f"Bearer {t_user}"}
    )
    assert res_user.status_code == 403

    res_admin = client.get(
        "/api/v1/admin/catalogo_ia",
        headers={"Authorization": f"Bearer {t_admin}"}
    )

    assert res_admin.status_code == 200
    assert isinstance(res_admin.json, list)

    yolo = next((m for m in res_admin.json if m["id_ia"] == env["ia_yolo"]), None)

    assert yolo is not None
    assert "modos" in yolo
    assert any(m["nombre_modo"] == "deteccion" for m in yolo["modos"])


def test_admin_crear_pipeline_persistencia_integral(client, app, db_session):
    """Comprueba la creación completa de un pipeline con varias etapas ordenadas."""
    env = setup_pipeline_env(app, db_session)

    with app.app_context():
        modo_det = IAModo.query.filter_by(
            id_ia=env["ia_yolo"],
            nombre_modo="deteccion"
        ).first()

        modo_pose = IAModo.query.filter_by(
            id_ia=env["ia_mp"],
            nombre_modo="pose"
        ).first()

        assert modo_det is not None
        assert modo_pose is not None

    token = create_access_token(
        identity=str(env["u_admin"]),
        additional_claims={"roles": ["admin"]}
    )

    payload = {
        "nombre": "  Pipeline auditoría admin  ",
        "descripcion": "Flujo creado desde la consola administrativa.",
        "publico": False,
        "habilitado": True,
        "etapas": [
            {
                "id_ia": env["ia_yolo"],
                "id_modo": modo_det.id_modo,
                "nombre": "Detección inicial",
                "descripcion": "Primera fase del flujo."
            },
            {
                "id_ia": env["ia_mp"],
                "id_modo": modo_pose.id_modo,
                "nombre": "",
                "descripcion": "Segunda fase del flujo."
            }
        ]
    }

    res = client.post(
        "/api/v1/admin/pipelines",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 201
    assert res.json["pipeline"]["nombre"] == "Pipeline auditoría admin"
    assert res.json["pipeline"]["publico"] is False
    assert len(res.json["pipeline"]["etapas"]) == 2

    id_pipeline = res.json["pipeline"]["id"]

    with app.app_context():
        pipeline = db_session.get(Pipeline, id_pipeline)
        etapas = PipelineEtapa.query.filter_by(
            id_pipeline=id_pipeline
        ).order_by(PipelineEtapa.orden).all()

        assert pipeline is not None
        assert pipeline.id_usuario == env["u_admin"]
        assert pipeline.publico == 0
        assert pipeline.habilitado == 1

        assert len(etapas) == 2
        assert [e.orden for e in etapas] == [1, 2]
        assert etapas[0].nombre == "Detección inicial"
        assert etapas[1].nombre.startswith("Etapa 2:")


def test_admin_crear_pipeline_rechaza_etapas_incoherentes(client, app, db_session):
    """Valida que no se puedan crear flujos con combinaciones IA-modo inválidas."""
    env = setup_pipeline_env(app, db_session)

    with app.app_context():
        modo_pose = IAModo.query.filter_by(
            id_ia=env["ia_mp"],
            nombre_modo="pose"
        ).first()

        modo_det = IAModo.query.filter_by(
            id_ia=env["ia_yolo"],
            nombre_modo="deteccion"
        ).first()

        assert modo_pose is not None
        assert modo_det is not None

        id_modo_pose = modo_pose.id_modo
        id_modo_det = modo_det.id_modo

    token = create_access_token(
        identity=str(env["u_admin"]),
        additional_claims={"roles": ["admin"]}
    )

    payload_modo_cruzado = {
        "nombre": "Modo cruzado",
        "etapas": [
            {
                "id_ia": env["ia_yolo"],
                "id_modo": id_modo_pose
            }
        ]
    }

    res_modo_cruzado = client.post(
        "/api/v1/admin/pipelines",
        json=payload_modo_cruzado,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res_modo_cruzado.status_code == 400
    assert "no pertenece" in res_modo_cruzado.json["mensaje"]

    with app.app_context():
        modo_det_bd = db_session.get(IAModo, id_modo_det)
        modo_det_bd.habilitado = 0
        db_session.commit()

    payload_modo_deshabilitado = {
        "nombre": "Modo deshabilitado",
        "etapas": [
            {
                "id_ia": env["ia_yolo"],
                "id_modo": id_modo_det
            }
        ]
    }

    res_modo_deshabilitado = client.post(
        "/api/v1/admin/pipelines",
        json=payload_modo_deshabilitado,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res_modo_deshabilitado.status_code == 400
    assert "deshabilitado" in res_modo_deshabilitado.json["mensaje"].lower()

    with app.app_context():
        ia_mp = db_session.get(IAModelo, env["ia_mp"])
        ia_mp.habilitada = 0
        db_session.commit()

    payload_modelo_deshabilitado = {
        "nombre": "Modelo deshabilitado",
        "etapas": [
            {
                "id_ia": env["ia_mp"],
                "id_modo": id_modo_pose
            }
        ]
    }

    res_modelo_deshabilitado = client.post(
        "/api/v1/admin/pipelines",
        json=payload_modelo_deshabilitado,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res_modelo_deshabilitado.status_code == 400
    assert "deshabilitado" in res_modelo_deshabilitado.json["mensaje"].lower()


def test_admin_crear_pipeline_payload_etapa_corrupto_devuelve_400(client, app, db_session):
    """
    Un payload malformado debe tratarse como error del cliente.
    Este caso evita que una etapa que no sea objeto provoque un 500 interno.
    """
    env = setup_pipeline_env(app, db_session)

    token = create_access_token(
        identity=str(env["u_admin"]),
        additional_claims={"roles": ["admin"]}
    )

    payload = {
        "nombre": "Payload corrupto",
        "etapas": ["valor-no-es-diccionario"]
    }

    res = client.post(
        "/api/v1/admin/pipelines",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 400
    assert "etapa" in res.json["mensaje"].lower()


def test_admin_actualizar_pipeline_reemplaza_etapas_sin_dejar_huerfanas(client, app, db_session):
    """Comprueba que editar un pipeline sustituye sus etapas de forma limpia."""
    env = setup_pipeline_env(app, db_session)

    with app.app_context():
        modo_pose = IAModo.query.filter_by(
            id_ia=env["ia_mp"],
            nombre_modo="pose"
        ).first()

        assert modo_pose is not None
        assert PipelineEtapa.query.filter_by(id_pipeline=env["p_pub"]).count() == 1

    token = create_access_token(
        identity=str(env["u_admin"]),
        additional_claims={"roles": ["admin"]}
    )

    payload = {
        "nombre": "Pipeline actualizado",
        "descripcion": "Nueva definición funcional del flujo.",
        "publico": False,
        "habilitado": False,
        "etapas": [
            {
                "id_ia": env["ia_mp"],
                "id_modo": modo_pose.id_modo,
                "nombre": "Pose final",
                "descripcion": "Etapa única tras la edición."
            }
        ]
    }

    res_404 = client.put(
        "/api/v1/admin/pipelines/999999",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_404.status_code == 404

    res = client.put(
        f"/api/v1/admin/pipelines/{env['p_pub']}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert res.json["pipeline"]["nombre"] == "Pipeline actualizado"
    assert res.json["pipeline"]["publico"] is False
    assert res.json["pipeline"]["habilitado"] is False
    assert len(res.json["pipeline"]["etapas"]) == 1

    with app.app_context():
        pipeline = db_session.get(Pipeline, env["p_pub"])
        etapas = PipelineEtapa.query.filter_by(id_pipeline=env["p_pub"]).all()

        assert pipeline.nombre == "Pipeline actualizado"
        assert pipeline.publico == 0
        assert pipeline.habilitado == 0

        assert len(etapas) == 1
        assert etapas[0].nombre == "Pose final"
        assert etapas[0].id_ia == env["ia_mp"]
        assert etapas[0].id_modo == modo_pose.id_modo
        assert etapas[0].orden == 1


def test_admin_eliminar_pipeline_elimina_o_deshabilita_segun_historial(client, app, db_session):
    """Valida el borrado físico solo cuando no existe historial asociado."""
    env = setup_pipeline_env(app, db_session)

    token = create_access_token(
        identity=str(env["u_admin"]),
        additional_claims={"roles": ["admin"]}
    )

    res_delete_sin_historial = client.delete(
        f"/api/v1/admin/pipelines/{env['p_priv']}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res_delete_sin_historial.status_code == 200

    with app.app_context():
        assert db_session.get(Pipeline, env["p_priv"]) is None
        assert PipelineEtapa.query.filter_by(id_pipeline=env["p_priv"]).count() == 0

        ejecucion = Ejecucion(
            id_usuario=env["u_pro"],
            id_pipeline=env["p_pub"],
            estado="completado"
        )
        db_session.add(ejecucion)
        db_session.commit()

    res_delete_con_historial = client.delete(
        f"/api/v1/admin/pipelines/{env['p_pub']}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res_delete_con_historial.status_code == 200
    assert "deshabilitado" in res_delete_con_historial.json["mensaje"].lower()

    with app.app_context():
        pipeline = db_session.get(Pipeline, env["p_pub"])

        assert pipeline is not None
        assert pipeline.habilitado == 0
        assert PipelineEtapa.query.filter_by(id_pipeline=env["p_pub"]).count() == 1


def test_ejecuciones_totales_admin_rbac_y_contenido_global(client, app, db_session):
    """Verifica que el histórico global solo sea visible para administración."""
    env = setup_pipeline_env(app, db_session)

    t_admin = create_access_token(
        identity=str(env["u_admin"]),
        additional_claims={"roles": ["admin"]}
    )
    t_user = create_access_token(
        identity=str(env["u_pro"]),
        additional_claims={"roles": ["usuario"]}
    )

    with app.app_context():
        ej_pro = Ejecucion(
            id_usuario=env["u_pro"],
            id_pipeline=env["p_pub"],
            estado="completado",
            duracion_ms=120
        )
        ej_basic = Ejecucion(
            id_usuario=env["u_basic"],
            id_pipeline=env["p_pub"],
            estado="error",
            mensaje_error_user="Error controlado"
        )

        db_session.add_all([ej_pro, ej_basic])
        db_session.commit()

        ids_creadas = {ej_pro.id_ejecucion, ej_basic.id_ejecucion}

    res_user = client.get(
        "/api/v1/ejecuciones_totales",
        headers={"Authorization": f"Bearer {t_user}"}
    )
    assert res_user.status_code == 403

    res_admin = client.get(
        "/api/v1/ejecuciones_totales",
        headers={"Authorization": f"Bearer {t_admin}"}
    )

    assert res_admin.status_code == 200

    ids_respuesta = {e["id"] for e in res_admin.json}

    assert ids_creadas.issubset(ids_respuesta)
    assert any(e["estado"] == "completado" for e in res_admin.json)
    assert any(e["estado"] == "error" for e in res_admin.json)


# ==============================================================================
# 7. PRUEBAS DE AUTORIZACIÓN SOBRE PIPELINES EJECUTABLES
# ==============================================================================
@patch("app.controllers.pipeline_controller.PipelineRunner.ejecutar_pipeline")
def test_analizar_no_ejecuta_pipeline_no_contratado(mock_runner, client, app, db_session):
    """
    Un usuario básico sin licencias no debe poder ejecutar un pipeline
    aunque conozca manualmente su identificador.
    """
    env = setup_pipeline_env(app, db_session)

    mock_runner.return_value = (
        [],
        [
            {
                "etapa": 1,
                "nombre_etapa": "No debería ejecutarse",
                "ia": "yolo",
                "modo": "deteccion",
                "imagenes": [],
                "datos": []
            }
        ]
    )

    token = create_access_token(
        identity=str(env["u_basic"]),
        additional_claims={"roles": ["usuario"]}
    )

    data = {
        "id_pipeline": str(env["p_pub"]),
        "config_personalizada": "{}",
        "imagen": (io.BytesIO(b"imagen falsa"), "entrada.jpg")
    }

    res = client.post(
        "/api/v1/analizar",
        data=data,
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 403
    mock_runner.assert_not_called()


@patch("app.controllers.pipeline_controller.PipelineRunner.ejecutar_pipeline")
def test_analizar_no_ejecuta_pipeline_privado_para_usuario_no_admin(mock_runner, client, app, db_session):
    """Un pipeline privado no debe ejecutarse desde una cuenta de usuario estándar."""
    env = setup_pipeline_env(app, db_session)

    mock_runner.return_value = (
        [],
        [
            {
                "etapa": 1,
                "nombre_etapa": "No debería ejecutarse",
                "ia": "mediapipe",
                "modo": "pose",
                "imagenes": [],
                "datos": []
            }
        ]
    )

    token = create_access_token(
        identity=str(env["u_pro"]),
        additional_claims={"roles": ["usuario"]}
    )

    data = {
        "id_pipeline": str(env["p_priv"]),
        "config_personalizada": "{}",
        "imagen": (io.BytesIO(b"imagen falsa"), "entrada.jpg")
    }

    res = client.post(
        "/api/v1/analizar",
        data=data,
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 403
    mock_runner.assert_not_called()


@patch("os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data='{"conf": 0.5}')
def test_configuracion_pipeline_no_expone_pipeline_privado(mock_file, mock_exists, client, app, db_session):
    """La configuración de un pipeline privado no debe exponerse a usuarios normales."""
    env = setup_pipeline_env(app, db_session)

    token = create_access_token(
        identity=str(env["u_pro"]),
        additional_claims={"roles": ["usuario"]}
    )

    res = client.get(
        f"/api/v1/configuracion_pipeline/{env['p_priv']}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code in (403, 404)
    mock_file.assert_not_called()


def test_listar_pipelines_no_concede_acceso_con_alquiler_programado(client, app, db_session):
    """
    Un alquiler activo pero con inicio futuro no debe habilitar pipelines todavía.
    Evita que una compra programada se trate como licencia vigente.
    """
    env = setup_pipeline_env(app, db_session)
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)

    with app.app_context():
        compra_programada = Alquila(
            id_usuario=env["u_basic"],
            id_ia=env["ia_yolo"],
            activo=1,
            periodo_inicio=ahora + timedelta(days=7),
            periodo_fin=ahora + timedelta(days=37)
        )
        db_session.add(compra_programada)
        db_session.commit()

    token = create_access_token(
        identity=str(env["u_basic"]),
        additional_claims={"roles": ["usuario"]}
    )

    res = client.get(
        "/api/v1/listado",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert all(p["id"] != env["p_pub"] for p in res.json)