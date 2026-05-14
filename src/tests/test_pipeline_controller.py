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