import os
import json
import uuid
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import get_jwt, jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from app import db
from app.services.pipeline_runner import PipelineRunner
from app.models import (
    Pipeline, Usuario, SuscripcionPlan, TipoPlan, Alquila, 
    PipelineEtapa, IAModelo, IAModo, Ejecucion, TemporalArchivo
)

pipeline_bp = Blueprint('pipeline', __name__)

# ==============================================================================
# CONFIGURACIÓN Y CONSTANTES DE SEGURIDAD
# ==============================================================================
DIRECTORIO_RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
CARPETA_EJECUCIONES = os.path.join(DIRECTORIO_RAIZ, 'execution_data')
os.makedirs(CARPETA_EJECUCIONES, exist_ok=True)

EXTENSIONES_PERMITIDAS = {'png', 'jpg', 'jpeg'}

def archivo_permitido(filename):
    """Valida la extensión del archivo contra la lista blanca permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in EXTENSIONES_PERMITIDAS

# ==============================================================================
# MANTENIMIENTO ASÍNCRONO (EJECUTADO POR PETICIÓN)
# ==============================================================================
@pipeline_bp.before_app_request
def tareas_mantenimiento_automaticas():
    """
    Gestiona el ciclo de vida de los recursos: expiración de archivos,
    renovación de servicios y cumplimiento de normativa de privacidad.
    """
    try:
        ahora_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        cambios_realizados = False
        
        # 1. Purga de archivos temporales con periodo de retención vencido
        archivos_caducados = TemporalArchivo.query.filter(TemporalArchivo.expira_en <= ahora_naive).all()
        for archivo in archivos_caducados:
            if archivo.ruta_servidor and os.path.exists(archivo.ruta_servidor):
                try: os.remove(archivo.ruta_servidor)
                except OSError: pass
            db.session.delete(archivo)
            cambios_realizados = True
            
        # 2. Gestión de estados de alquileres de IA
        alquileres_vencidos = Alquila.query.filter(Alquila.activo == 1, Alquila.periodo_fin <= ahora_naive).all()
        for alquiler in alquileres_vencidos:
            if alquiler.renovacion_auto == 1:
                alquiler.periodo_inicio = ahora_naive
                alquiler.periodo_fin = ahora_naive + timedelta(days=30)
            else:
                alquiler.activo = 0
            cambios_realizados = True
            
        # 3. Control de vigencia de planes de suscripción
        suscripciones_vencidas = SuscripcionPlan.query.filter(SuscripcionPlan.activo == 1, SuscripcionPlan.fecha_fin <= ahora_naive).all()
        for sub in suscripciones_vencidas:
            if sub.renovacion_auto == 1:
                sub.fecha_inicio = ahora_naive
                sub.fecha_fin = ahora_naive + timedelta(days=30)
            else:
                sub.activo = 0
            cambios_realizados = True
            
        # 4. Anonimización de cuentas eliminadas tras periodo legal (30 días)
        limite_olvido = ahora_naive - timedelta(days=30)
        usuarios_para_anonimizar = Usuario.query.filter(Usuario.estado == 'borrada', Usuario.borrado_en <= limite_olvido).all()
        for u in usuarios_para_anonimizar:
            u.username = f"anon_{u.id_usuario}"
            u.email = f"deleted_{u.id_usuario}@explorer.local"
            u.password_hash = "ACCOUNT_DELETED"
            u.estado = 'anonimizado'
            u.nombre_visible = "Usuario Eliminado"
            cambios_realizados = True

        if cambios_realizados:
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR MANTENIMIENTO] {str(e)}")

# ==============================================================================
# GESTIÓN DE PIPELINES Y CONFIGURACIÓN
# ==============================================================================
@pipeline_bp.route('/listado', methods=['GET'])
@jwt_required()
def listar_pipelines():
    """Filtra y retorna pipelines accesibles según rol o servicios contratados."""
    try:
        claims = get_jwt()
        usuario_id = get_jwt_identity()
        ahora_naive = datetime.now(timezone.utc).replace(tzinfo=None)

        if "admin" in claims.get("roles", []):
            pipelines = Pipeline.query.filter_by(habilitado=1).all()
            return jsonify([{"id": p.id_pipeline, "nombre": p.nombre} for p in pipelines]), 200

        es_pro = SuscripcionPlan.query.join(TipoPlan).filter(
            SuscripcionPlan.id_usuario == usuario_id,
            SuscripcionPlan.activo == 1,
            TipoPlan.nombre == 'Pro',
            SuscripcionPlan.fecha_inicio <= ahora_naive,
            (SuscripcionPlan.fecha_fin >= ahora_naive) | (SuscripcionPlan.fecha_fin.is_(None))
        ).first() is not None

        if es_pro:
            pipelines = Pipeline.query.filter_by(publico=1, habilitado=1).all()
        else:
            alquileres = Alquila.query.filter(Alquila.id_usuario == usuario_id, Alquila.activo == 1).all()
            ias_contratadas = {a.id_ia for a in alquileres}
            pipelines_disponibles = Pipeline.query.filter_by(publico=1, habilitado=1).all()
            pipelines = [p for p in pipelines_disponibles if {e.id_ia for e in p.etapas}.issubset(ias_contratadas)]

        return jsonify([{"id": p.id_pipeline, "nombre": p.nombre} for p in pipelines]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@pipeline_bp.route('/detalles_completos', methods=['GET'])
@jwt_required()
def listar_detalles_admin():
    """Endpoint de auditoría para obtener el mapeo técnico de pipelines (Admin Only)."""
    if "admin" not in get_jwt().get("roles", []):
        return jsonify({"mensaje": "Acceso denegado"}), 403

    try:
        pipelines = Pipeline.query.all()
        resultado = []
        for p in pipelines:
            resultado.append({
                "id": p.id_pipeline,
                "nombre": p.nombre,
                "publico": p.publico,
                "descripcion": p.descripcion,
                "etapas": [{
                    "orden": e.orden,
                    "nombre_etapa": e.nombre,
                    "ia": e.modelo.nombre if e.modelo else "N/A",
                    "modo": e.modo.nombre_modo if e.modo else "N/A"
                } for e in p.etapas]
            })
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@pipeline_bp.route('/configuracion_pipeline/<int:id_pipeline>', methods=['GET'])
@jwt_required()
def obtener_configuracion_completa(id_pipeline):
    """Extrae los esquemas JSON de configuración predeterminada para cada etapa."""
    try:
        etapas = PipelineEtapa.query.filter_by(id_pipeline=id_pipeline).order_by(PipelineEtapa.orden).all()
        config_completa = {}
        for e in etapas:
            modo = IAModo.query.get(e.id_modo)
            config_etapa = {}
            if modo and modo.config_predeterminada and os.path.exists(modo.config_predeterminada):
                with open(modo.config_predeterminada, 'r') as f:
                    config_etapa = json.load(f)
            config_completa[f"etapa_{e.orden}"] = config_etapa
        return jsonify(config_completa), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==============================================================================
# MOTOR DE PROCESAMIENTO E IA
# ==============================================================================
@pipeline_bp.route('/analizar', methods=['POST'])
@jwt_required()
def analizar_imagen():
    """Orquestador de ejecución: valida integridad, procesa y persiste resultados."""
    usuario_id = get_jwt_identity()
    ahora_utc = datetime.now(timezone.utc)
    ahora_naive = ahora_utc.replace(tzinfo=None)
    
    if 'imagen' not in request.files or not request.form.get('id_pipeline'):
        return jsonify({"status": "error", "mensaje": "Parámetros insuficientes"}), 400
        
    imagen_file = request.files['imagen']
    id_pipeline = request.form.get('id_pipeline')
    config_usuario_str = request.form.get('config_personalizada')

    if imagen_file.filename == '' or not archivo_permitido(imagen_file.filename):
        return jsonify({"status": "error", "mensaje": "Archivo no permitido"}), 400

    es_pro = SuscripcionPlan.query.join(TipoPlan).filter(
        SuscripcionPlan.id_usuario == usuario_id, SuscripcionPlan.activo == 1, TipoPlan.nombre == 'Pro'
    ).first() is not None
    fecha_expiracion = ahora_naive + (timedelta(days=7) if es_pro else timedelta(minutes=5))

    nueva_ejecucion = Ejecucion(id_usuario=usuario_id, id_pipeline=id_pipeline, estado='procesando', config_aplicada=config_usuario_str)
    db.session.add(nueva_ejecucion)
    db.session.commit()

    start_time = datetime.now()
    try:
        folder_path = os.path.join(CARPETA_EJECUCIONES, f"exec_{nueva_ejecucion.id_ejecucion}")
        os.makedirs(folder_path, exist_ok=True)
        
        prefijo = f"u{usuario_id}_t{int(ahora_utc.timestamp())}"
        filename = secure_filename(f"{prefijo}_{imagen_file.filename}")
        ruta_input = os.path.join(folder_path, filename)
        imagen_file.save(ruta_input)

        db.session.add(TemporalArchivo(id_ejecucion=nueva_ejecucion.id_ejecucion, tipo="imagen_original", 
                                      ruta_servidor=ruta_input, token_descarga=str(uuid.uuid4()), expira_en=fecha_expiracion))

        config_dict = json.loads(config_usuario_str) if config_usuario_str else {}
        _, analisis = PipelineRunner.ejecutar_pipeline(int(id_pipeline), ruta_input, config_dict, prefijo)
        
        for etapa in analisis:
            tokens_img = []
            for img_name in etapa["imagenes"]:
                token = str(uuid.uuid4())
                ruta_full = os.path.join(folder_path, img_name)
                db.session.add(TemporalArchivo(id_ejecucion=nueva_ejecucion.id_ejecucion, tipo="resultado_imagen", 
                                              ruta_servidor=ruta_full, token_descarga=token, expira_en=fecha_expiracion))
                tokens_img.append(token)
            etapa["imagenes"] = tokens_img

            json_name = f"{prefijo}_data_e{etapa['etapa']}.json"
            ruta_json = os.path.join(folder_path, json_name)
            with open(ruta_json, 'w', encoding='utf-8') as f:
                json.dump(etapa["datos"], f, indent=4, ensure_ascii=False)
            
            token_json = str(uuid.uuid4())
            db.session.add(TemporalArchivo(id_ejecucion=nueva_ejecucion.id_ejecucion, tipo="resultado_json", 
                                          ruta_servidor=ruta_json, token_descarga=token_json, expira_en=fecha_expiracion))
            etapa["token_json_descarga"] = token_json

        nueva_ejecucion.estado = 'completado'
        nueva_ejecucion.duracion_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        db.session.commit()
        return jsonify({"status": "success", "resultados_etapas": analisis}), 200

    except Exception as e:
        db.session.rollback()
        nueva_ejecucion.estado = 'error'
        nueva_ejecucion.mensaje_error_user = str(e)
        db.session.commit()
        return jsonify({"status": "error", "mensaje": str(e)}), 500

# ==============================================================================
# AUDITORÍA Y RESULTADOS
# ==============================================================================
@pipeline_bp.route('/outputs/<token>')
def serve_output(token):
    """Acceso seguro a recursos mediante abstracción por token y validación de expiración."""
    archivo = TemporalArchivo.query.filter_by(token_descarga=token).first()
    ahora_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    
    if not archivo or (archivo.expira_en and archivo.expira_en <= ahora_naive):
        return jsonify({"error": "Archivo no disponible o expirado"}), 404
        
    return send_file(archivo.ruta_servidor)

@pipeline_bp.route('/historial', methods=['GET'])
@jwt_required()
def historial_ejecuciones():
    """Retorna el registro histórico de operaciones del usuario autenticado."""
    usuario_id = get_jwt_identity()
    ahora_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    ejecuciones = Ejecucion.query.filter_by(id_usuario=usuario_id).order_by(Ejecucion.creado_en.desc()).all()
    
    resultado = []
    for ej in ejecuciones:
        pipe = Pipeline.query.get(ej.id_pipeline)
        activos = TemporalArchivo.query.filter(TemporalArchivo.id_ejecucion == ej.id_ejecucion, 
                                               TemporalArchivo.expira_en > ahora_naive).first()
        resultado.append({
            "id": ej.id_ejecucion,
            "pipeline": pipe.nombre if pipe else "Desconocido",
            "fecha": ej.creado_en.strftime("%d/%m/%Y %H:%M"),
            "estado": ej.estado,
            "duracion": f"{ej.duracion_ms} ms" if ej.duracion_ms else "-",
            "error": ej.mensaje_error_user,
            "archivos_disponibles": bool(activos)
        })
    return jsonify(resultado), 200

@pipeline_bp.route('/ejecucion/<int:id_ejecucion>/archivos', methods=['GET'])
@jwt_required()
def obtener_archivos_ejecucion(id_ejecucion):
    """Estructura los recursos generados para una ejecución específica."""
    usuario_id = get_jwt_identity()
    ahora_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    
    ejecucion = Ejecucion.query.filter_by(id_ejecucion=id_ejecucion, id_usuario=usuario_id).first()
    if not ejecucion:
        return jsonify({"error": "Acceso denegado"}), 403
        
    archivos = TemporalArchivo.query.filter(TemporalArchivo.id_ejecucion == id_ejecucion, 
                                           TemporalArchivo.expira_en > ahora_naive).all()
    
    etapas = PipelineEtapa.query.filter_by(id_pipeline=ejecucion.id_pipeline).order_by(PipelineEtapa.orden).all()
    datos_etapas, img_list, idx_etapa, img_orig = [], [], 0, None

    for arch in archivos:
        info = {"token": arch.token_descarga, "nombre": os.path.basename(arch.ruta_servidor)}
        if arch.tipo == "imagen_original": img_orig = info
        elif arch.tipo == "resultado_imagen": img_list.append(info)
        elif arch.tipo == "resultado_json":
            etapa_label = etapas[idx_etapa].nombre if idx_etapa < len(etapas) else f"Etapa {idx_etapa+1}"
            datos_etapas.append({"nombre_etapa": etapa_label, "imagenes": img_list, "json": info})
            img_list, idx_etapa = [], idx_etapa + 1
            
    return jsonify({"imagen_original": img_orig, "etapas": datos_etapas}), 200

# ==============================================================================
# ADMINISTRACIÓN AVANZADA
# ==============================================================================
@pipeline_bp.route('/ejecuciones_totales', methods=['GET'])
@jwt_required()
def listar_ejecuciones_admin():
    """Historial global consolidado para auditoría administrativa."""
    if "admin" not in get_jwt().get("roles", []):
        return jsonify({"mensaje": "Acceso denegado"}), 403

    ejecuciones = db.session.query(Ejecucion, Usuario.username, Pipeline.nombre)\
        .join(Usuario, Ejecucion.id_usuario == Usuario.id_usuario)\
        .join(Pipeline, Ejecucion.id_pipeline == Pipeline.id_pipeline)\
        .order_by(Ejecucion.creado_en.desc()).all()

    return jsonify([{
        "id": ej.id_ejecucion, "usuario": uname, "pipeline": pnombre, "estado": ej.estado,
        "fecha": ej.creado_en.strftime("%d/%m/%Y %H:%M"), "duracion": ej.duracion_ms or "-",
        "error": ej.mensaje_error_user
    } for ej, uname, pnombre in ejecuciones]), 200

@pipeline_bp.route('/admin/cambiar_estado/<int:id_usuario>', methods=['POST'])
@jwt_required()
def admin_cambiar_estado(id_usuario):
    """Gestión de estados de cuenta (bloqueo/activación) desde el panel admin."""
    if 'admin' not in get_jwt().get('roles', []):
        return jsonify({"mensaje": "Acceso denegado"}), 403
    
    usuario = Usuario.query.get(id_usuario)
    if not usuario or usuario.id_usuario == int(get_jwt_identity()):
        return jsonify({"mensaje": "Operación no válida"}), 400

    estado = request.get_json().get('estado')
    usuario.estado = estado
    usuario.borrado_en = datetime.now(timezone.utc).replace(tzinfo=None) if estado == 'borrada' else None
    db.session.commit()
    return jsonify({"status": "success", "mensaje": "Estado actualizado"}), 200