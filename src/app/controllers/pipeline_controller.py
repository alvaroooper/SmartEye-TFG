import os
import json
import uuid
from datetime import datetime, timedelta, timezone
from app.utils.fechas import ahora_utc_naive, formatear_fecha_local
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
# CONFIGURACIÓN DEL ENTORNO DE EJECUCIÓN
# ==============================================================================
DIRECTORIO_RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
CARPETA_EJECUCIONES = os.path.join(DIRECTORIO_RAIZ, 'execution_data')
os.makedirs(CARPETA_EJECUCIONES, exist_ok=True)

EXTENSIONES_PERMITIDAS = {'png', 'jpg', 'jpeg'}

def archivo_permitido(filename: str) -> bool:
    """Valida la extensión del archivo entrante contra una lista blanca segura."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in EXTENSIONES_PERMITIDAS

# ==============================================================================
# RUTINAS DE MANTENIMIENTO ASÍNCRONO
# ==============================================================================
@pipeline_bp.before_app_request
def tareas_mantenimiento_automaticas():
    """
    Controlador de ciclo de vida (Lifecycle Hooks).
    Se ejecuta de forma asíncrona previo a cada petición para gestionar 
    la recolección de basura (archivos expirados) y la coherencia de contratos.
    """
    try:
        ahora_naive = ahora_utc_naive()
        cambios_realizados = False
        
        # 1. Purga de artefactos temporales (Data Retention Policy)
        archivos_caducados = TemporalArchivo.query.filter(TemporalArchivo.expira_en <= ahora_naive).all()
        for archivo in archivos_caducados:
            if archivo.ruta_servidor and os.path.exists(archivo.ruta_servidor):
                try: 
                    os.remove(archivo.ruta_servidor)
                except OSError: 
                    pass
            db.session.delete(archivo)
            cambios_realizados = True
            
        # 2. Resolución de licencias de uso temporal (Alquileres IA)
        alquileres_vencidos = Alquila.query.filter(Alquila.activo == 1, Alquila.periodo_fin <= ahora_naive).all()
        for alquiler in alquileres_vencidos:
            if alquiler.renovacion_auto == 1:
                alquiler.periodo_inicio = ahora_naive
                alquiler.periodo_fin = ahora_naive + timedelta(days=30)
            else:
                alquiler.activo = 0
            cambios_realizados = True
            
        # 3. Resolución de contratos de suscripción
        suscripciones_vencidas = SuscripcionPlan.query.filter(SuscripcionPlan.activo == 1, SuscripcionPlan.fecha_fin <= ahora_naive).all()
        for sub in suscripciones_vencidas:
            if sub.renovacion_auto == 1:
                sub.fecha_inicio = ahora_naive
                sub.fecha_fin = ahora_naive + timedelta(days=30)
            else:
                sub.activo = 0
            cambios_realizados = True
            
        # 4. Protocolo de Anonimización (Cumplimiento RGPD - Derecho al Olvido)
        limite_olvido = ahora_naive - timedelta(days=30)
        usuarios_para_anonimizar = Usuario.query.filter(Usuario.estado == 'borrada', Usuario.borrado_en <= limite_olvido).all()
        for u in usuarios_para_anonimizar:
            u.username = f"anon_{u.id_usuario}"
            u.email = f"deleted_{u.id_usuario}@explorer.local"
            u.password_hash = "ACCOUNT_DELETED"
            u.estado = 'anonimizado'
            u.nombre_visible = "Identidad Anonimizada"
            cambios_realizados = True

        if cambios_realizados:
            db.session.commit()
            
    except Exception as e:
        db.session.rollback()
        # En producción, este print debería ser sustituido por un logger estructurado
        print(f"[ERROR SUBSISTEMA MANTENIMIENTO] {str(e)}")

# ==============================================================================
# GESTIÓN DE CATÁLOGO Y CONFIGURACIONES (PIPELINES)
# ==============================================================================
@pipeline_bp.route('/listado', methods=['GET'])
@jwt_required()
def listar_pipelines():
    """
    Filtra dinámicamente los flujos de análisis disponibles basándose en 
    el perfil de suscripción o en licencias temporales vigentes.
    """
    try:
        usuario_id = obtener_usuario_id_actual()
        ahora_naive = ahora_utc_naive()

        if usuario_id is None:
            return jsonify({"mensaje": "Identidad de usuario inválida."}), 401

        if es_admin_actual():
            pipelines = Pipeline.query.filter_by(habilitado=1).all()
            return jsonify([
                {
                    "id": p.id_pipeline,
                    "nombre": p.nombre
                }
                for p in pipelines
            ]), 200

        if usuario_tiene_pro_vigente(usuario_id, ahora_naive):
            pipelines = Pipeline.query.filter_by(publico=1, habilitado=1).all()
        else:
            ias_contratadas = obtener_ias_alquiladas_vigentes(usuario_id, ahora_naive)
            pipelines_disponibles = Pipeline.query.filter_by(publico=1, habilitado=1).all()

            pipelines = [
                pipeline
                for pipeline in pipelines_disponibles
                if {etapa.id_ia for etapa in pipeline.etapas}.issubset(ias_contratadas)
            ]

        return jsonify([
            {
                "id": p.id_pipeline,
                "nombre": p.nombre
            }
            for p in pipelines
        ]), 200

    except Exception as e:
        return jsonify({"error": f"Fallo en la resolución de dependencias: {str(e)}"}), 500

@pipeline_bp.route('/detalles_completos', methods=['GET'])
@jwt_required()
def listar_detalles_admin():
    """
    Endpoint de introspección técnica. 
    Retorna el mapeo completo de flujos y motores subyacentes para la consola administrativa.
    """
    if "admin" not in get_jwt().get("roles", []):
        return jsonify({"mensaje": "Violación de acceso: Privilegios insuficientes"}), 403

    try:
        pipelines = Pipeline.query.all()
        resultado = [serializar_pipeline_admin(p) for p in pipelines]
        return jsonify(resultado), 200

    except Exception as e:
        return jsonify({"error": f"Error en introspección de base de datos: {str(e)}"}), 500

@pipeline_bp.route('/configuracion_pipeline/<int:id_pipeline>', methods=['GET'])
@jwt_required()
def obtener_configuracion_completa(id_pipeline):
    """Lectura y ensamblado de los esquemas JSON de configuración por cada etapa del flujo."""
    try:
        usuario_id = obtener_usuario_id_actual()
        ahora_naive = ahora_utc_naive()

        if usuario_id is None:
            return jsonify({"mensaje": "Identidad de usuario inválida."}), 401

        autorizado, mensaje, codigo_estado, _ = comprobar_acceso_pipeline(
            id_pipeline,
            usuario_id,
            ahora_naive
        )

        if not autorizado:
            return jsonify({"mensaje": mensaje}), codigo_estado

        etapas = PipelineEtapa.query.filter_by(
            id_pipeline=id_pipeline
        ).order_by(PipelineEtapa.orden).all()

        config_completa = {}

        for etapa in etapas:
            modo = db.session.get(IAModo, etapa.id_modo)
            config_etapa = {}

            if modo and modo.config_predeterminada and os.path.exists(modo.config_predeterminada):
                with open(modo.config_predeterminada, 'r') as f:
                    config_etapa = json.load(f)

            config_completa[f"etapa_{etapa.orden}"] = config_etapa

        return jsonify(config_completa), 200

    except Exception as e:
        return jsonify({"error": f"Fallo en la lectura de esquemas: {str(e)}"}), 500
    
# ==============================================================================
# GESTIÓN ADMINISTRATIVA DE PIPELINES
# ==============================================================================

def es_admin_actual() -> bool:
    """Comprueba si el JWT actual pertenece a un usuario administrador."""
    return "admin" in get_jwt().get("roles", [])

def obtener_usuario_id_actual():
    """Devuelve el identificador numérico del usuario autenticado."""
    try:
        return int(get_jwt_identity())
    except (TypeError, ValueError):
        return None


def usuario_tiene_pro_vigente(usuario_id, ahora_naive):
    """Comprueba si el usuario tiene una suscripción Pro activa en este momento."""
    return db.session.query(SuscripcionPlan).join(TipoPlan).filter(
        SuscripcionPlan.id_usuario == usuario_id,
        SuscripcionPlan.activo == 1,
        TipoPlan.nombre == 'Pro',
        SuscripcionPlan.fecha_inicio <= ahora_naive,
        (SuscripcionPlan.fecha_fin >= ahora_naive) | (SuscripcionPlan.fecha_fin.is_(None))
    ).first() is not None


def obtener_ias_alquiladas_vigentes(usuario_id, ahora_naive):
    """Devuelve las IA contratadas cuyo periodo de uso ya está vigente."""
    alquileres = Alquila.query.filter(
        Alquila.id_usuario == usuario_id,
        Alquila.activo == 1,
        (Alquila.periodo_inicio <= ahora_naive) | (Alquila.periodo_inicio.is_(None)),
        (Alquila.periodo_fin >= ahora_naive) | (Alquila.periodo_fin.is_(None))
    ).all()

    return {alquiler.id_ia for alquiler in alquileres}


def comprobar_acceso_pipeline(id_pipeline, usuario_id, ahora_naive):
    """
    Comprueba si el usuario puede acceder a un pipeline concreto.
    Admin: acceso total.
    Pro: acceso a pipelines públicos.
    Básico: acceso solo si tiene vigentes todas las IA requeridas.
    """
    pipeline = db.session.get(Pipeline, id_pipeline)

    if not pipeline:
        return False, "Pipeline no encontrado.", 404, None

    if not pipeline.habilitado:
        return False, "Pipeline no disponible.", 404, pipeline

    if es_admin_actual():
        return True, None, 200, pipeline

    if not pipeline.publico:
        return False, "No tienes permisos para acceder a este pipeline.", 403, pipeline

    etapas = PipelineEtapa.query.filter_by(id_pipeline=id_pipeline).all()

    if not etapas:
        return False, "El pipeline no tiene etapas configuradas.", 400, pipeline

    if usuario_tiene_pro_vigente(usuario_id, ahora_naive):
        return True, None, 200, pipeline

    ias_requeridas = {etapa.id_ia for etapa in etapas}
    ias_alquiladas = obtener_ias_alquiladas_vigentes(usuario_id, ahora_naive)

    if ias_requeridas.issubset(ias_alquiladas):
        return True, None, 200, pipeline

    return False, "No tienes acceso a todas las IA requeridas por este pipeline.", 403, pipeline

def serializar_pipeline_admin(pipeline):
    """Convierte un pipeline completo a JSON para la consola administrativa."""
    etapas_ordenadas = sorted(pipeline.etapas, key=lambda e: e.orden)

    return {
        "id": pipeline.id_pipeline,
        "nombre": pipeline.nombre,
        "descripcion": pipeline.descripcion,
        "publico": bool(pipeline.publico),
        "habilitado": bool(pipeline.habilitado),
        "etapas": [
            {
                "id_etapa": e.id_etapa,
                "orden": e.orden,
                "nombre_etapa": e.nombre,
                "descripcion": e.descripcion,
                "id_ia": e.id_ia,
                "id_modo": e.id_modo,
                "ia": e.modelo.nombre if e.modelo else "N/A",
                "modo": e.modo.nombre_modo if e.modo else "N/A"
            }
            for e in etapas_ordenadas
        ]
    }


def validar_etapas_pipeline(etapas):
    """
    Valida que las etapas recibidas sean correctas y que cada modo pertenezca
    realmente al modelo de IA indicado.
    """
    if not isinstance(etapas, list) or len(etapas) == 0:
        return False, "El pipeline debe contener al menos una etapa."

    etapas_validadas = []

    for indice, etapa in enumerate(etapas, start=1):
        if not isinstance(etapa, dict):
            return False, f"La etapa {indice} debe ser un objeto JSON válido."

        try:
            id_ia = int(etapa.get("id_ia"))
            id_modo = int(etapa.get("id_modo"))
        except (TypeError, ValueError):
            return False, "Cada etapa debe incluir un modelo de IA y un modo válidos."

        modelo = db.session.get(IAModelo, id_ia)

        if not modelo or not modelo.habilitada:
            return False, f"El modelo de IA indicado en la etapa {indice} no existe o está deshabilitado."

        modo = IAModo.query.filter_by(id_modo=id_modo, id_ia=id_ia).first()

        if not modo:
            return False, f"El modo indicado en la etapa {indice} no pertenece al modelo seleccionado."

        if not modo.habilitado:
            return False, f"El modo '{modo.nombre_modo}' está deshabilitado."

        etapas_validadas.append({
            "id_ia": id_ia,
            "id_modo": id_modo,
            "orden": indice,
            "nombre": etapa.get("nombre") or f"Etapa {indice}: {modelo.nombre} - {modo.nombre_modo}",
            "descripcion": etapa.get("descripcion")
        })

    return True, etapas_validadas


@pipeline_bp.route('/admin/catalogo_ia', methods=['GET'])
@jwt_required()
def obtener_catalogo_ia_admin():
    """
    Devuelve los modelos de IA y modos ya creados para construir pipelines
    desde la interfaz del administrador.
    """
    if not es_admin_actual():
        return jsonify({"mensaje": "Privilegios insuficientes"}), 403

    try:
        modelos = IAModelo.query.order_by(IAModelo.nombre).all()

        resultado = [
            {
                "id_ia": modelo.id_ia,
                "nombre": modelo.nombre,
                "descripcion": modelo.descripcion,
                "habilitada": bool(modelo.habilitada),
                "modos": [
                    {
                        "id_modo": modo.id_modo,
                        "nombre_modo": modo.nombre_modo,
                        "descripcion": modo.descripcion,
                        "habilitado": bool(modo.habilitado)
                    }
                    for modo in modelo.modos
                ]
            }
            for modelo in modelos
        ]

        return jsonify(resultado), 200

    except Exception as e:
        return jsonify({"error": f"Error al cargar catálogo IA: {str(e)}"}), 500


@pipeline_bp.route('/admin/pipelines', methods=['POST'])
@jwt_required()
def crear_pipeline_admin():
    """
    Crea un nuevo pipeline con sus etapas desde la consola administrativa.
    """
    if not es_admin_actual():
        return jsonify({"mensaje": "Privilegios insuficientes"}), 403

    try:
        data = request.get_json() or {}

        nombre = (data.get("nombre") or "").strip()
        descripcion = data.get("descripcion")
        publico = bool(data.get("publico", True))
        habilitado = bool(data.get("habilitado", True))
        etapas = data.get("etapas", [])

        if not nombre:
            return jsonify({"mensaje": "El nombre del pipeline es obligatorio."}), 400

        valido, resultado_etapas = validar_etapas_pipeline(etapas)

        if not valido:
            return jsonify({"mensaje": resultado_etapas}), 400

        nuevo_pipeline = Pipeline(
            id_usuario=int(get_jwt_identity()),
            nombre=nombre,
            descripcion=descripcion,
            publico=1 if publico else 0,
            habilitado=1 if habilitado else 0
        )

        db.session.add(nuevo_pipeline)
        db.session.flush()

        for etapa in resultado_etapas:
            db.session.add(PipelineEtapa(
                id_pipeline=nuevo_pipeline.id_pipeline,
                id_ia=etapa["id_ia"],
                id_modo=etapa["id_modo"],
                orden=etapa["orden"],
                nombre=etapa["nombre"],
                descripcion=etapa["descripcion"]
            ))

        db.session.commit()

        return jsonify({
            "mensaje": "Pipeline creado correctamente.",
            "pipeline": serializar_pipeline_admin(nuevo_pipeline)
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al crear pipeline: {str(e)}"}), 500


@pipeline_bp.route('/admin/pipelines/<int:id_pipeline>', methods=['PUT'])
@jwt_required()
def actualizar_pipeline_admin(id_pipeline):
    """
    Actualiza los datos generales y las etapas de un pipeline existente.
    """
    if not es_admin_actual():
        return jsonify({"mensaje": "Privilegios insuficientes"}), 403

    try:
        pipeline = db.session.get(Pipeline, id_pipeline)

        if not pipeline:
            return jsonify({"mensaje": "Pipeline no encontrado."}), 404

        data = request.get_json() or {}

        nombre = (data.get("nombre") or "").strip()

        if not nombre:
            return jsonify({"mensaje": "El nombre del pipeline es obligatorio."}), 400

        etapas = data.get("etapas", [])
        valido, resultado_etapas = validar_etapas_pipeline(etapas)

        if not valido:
            return jsonify({"mensaje": resultado_etapas}), 400

        pipeline.nombre = nombre
        pipeline.descripcion = data.get("descripcion")
        pipeline.publico = 1 if bool(data.get("publico", True)) else 0
        pipeline.habilitado = 1 if bool(data.get("habilitado", True)) else 0

        # Reemplazo completo de etapas.
        # Gracias a cascade="all, delete-orphan", SQLAlchemy eliminará las antiguas.
        pipeline.etapas.clear()
        db.session.flush()

        for etapa in resultado_etapas:
            db.session.add(PipelineEtapa(
                id_pipeline=pipeline.id_pipeline,
                id_ia=etapa["id_ia"],
                id_modo=etapa["id_modo"],
                orden=etapa["orden"],
                nombre=etapa["nombre"],
                descripcion=etapa["descripcion"]
            ))

        db.session.commit()

        return jsonify({
            "mensaje": "Pipeline actualizado correctamente.",
            "pipeline": serializar_pipeline_admin(pipeline)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al actualizar pipeline: {str(e)}"}), 500


@pipeline_bp.route('/admin/pipelines/<int:id_pipeline>', methods=['DELETE'])
@jwt_required()
def eliminar_pipeline_admin(id_pipeline):
    """
    Elimina un pipeline si no tiene ejecuciones asociadas.
    Si tiene historial, se deshabilita para no romper la integridad referencial.
    """
    if not es_admin_actual():
        return jsonify({"mensaje": "Privilegios insuficientes"}), 403

    try:
        pipeline = db.session.get(Pipeline, id_pipeline)

        if not pipeline:
            return jsonify({"mensaje": "Pipeline no encontrado."}), 404

        ejecuciones_asociadas = Ejecucion.query.filter_by(id_pipeline=id_pipeline).first()

        if ejecuciones_asociadas:
            pipeline.habilitado = 0
            db.session.commit()

            return jsonify({
                "mensaje": "El pipeline tenía ejecuciones asociadas, por lo que se ha deshabilitado en lugar de eliminarse físicamente."
            }), 200

        db.session.delete(pipeline)
        db.session.commit()

        return jsonify({"mensaje": "Pipeline eliminado correctamente."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error al eliminar pipeline: {str(e)}"}), 500

# ==============================================================================
# MOTOR CENTRAL DE PROCESAMIENTO E INFERENCIA (CORE)
# ==============================================================================
@pipeline_bp.route('/analizar', methods=['POST'])
@jwt_required()
def analizar_imagen():
    """
    Orquestador principal de inferencia de visión artificial.
    
    Aplica una estrategia de 'API Hardening' mediante la validación estricta de 
    payloads, gestión de aislamiento de workspace por ejecución y políticas 
    dinámicas de expiración de activos (TTL) según el nivel de suscripción.
    """
    usuario_id = get_jwt_identity()
    ahora_naive = ahora_utc_naive()
    ahora_utc = ahora_naive.replace(tzinfo=timezone.utc)
    
    if usuario_id is None:
        return jsonify({
            "status": "error",
            "mensaje": "Identidad de usuario inválida."
        }), 401
    # --------------------------------------------------------------------------
    # 1. VALIDACIÓN PRELIMINAR Y CAPTURA DE INPUTS
    # --------------------------------------------------------------------------
    id_pipeline = request.form.get('id_pipeline')
    config_usuario_str = request.form.get('config_personalizada')
    
    # Guardia de seguridad: Validación de presencia de binario y metadatos
    if 'imagen' not in request.files or not id_pipeline:
        return jsonify({
            "status": "error", 
            "mensaje": "Payload incompleto: Se requiere el binario de la imagen e identificador de flujo."
        }), 400
        
    imagen_file = request.files.get('imagen')

    # Validación de integridad del objeto FileStorage
    if not imagen_file or imagen_file.filename == '':
        return jsonify({"status": "error", "mensaje": "No se ha detectado ningún archivo válido."}), 400

    # Auditoría de extensión para prevención de inyección de archivos maliciosos
    if not archivo_permitido(imagen_file.filename):
        return jsonify({
            "status": "error", 
            "mensaje": "Formato de archivo no soportado o potencialmente inseguro."
        }), 400

    # --------------------------------------------------------------------------
    # 2. BASTIONADO DE CONFIGURACIÓN (JSON SANITIZATION)
    # --------------------------------------------------------------------------
    # Bloque aislado para evitar que errores de formato en el cliente disparen un 500
    try:
        config_dict = json.loads(config_usuario_str) if config_usuario_str else {}
    except (json.JSONDecodeError, TypeError):
        return jsonify({
            "status": "error", 
            "mensaje": "La configuración personalizada tiene un formato JSON inválido."
        }), 400
    try:
        id_pipeline_int = int(id_pipeline)
    except (TypeError, ValueError):
        return jsonify({
            "status": "error",
            "mensaje": "El identificador del pipeline no es válido."
        }), 400

    autorizado, mensaje, codigo_estado, _ = comprobar_acceso_pipeline(
        id_pipeline_int,
        usuario_id,
        ahora_naive
    )

    if not autorizado:
        return jsonify({
            "status": "error",
            "mensaje": mensaje
        }), codigo_estado
    # --------------------------------------------------------------------------
    # 3. DETERMINACIÓN DE POLÍTICAS DE RETENCIÓN (TTL)
    # --------------------------------------------------------------------------
    # Lógica de negocio: Los usuarios Pro disponen de una ventana de persistencia mayor
    es_pro = usuario_tiene_pro_vigente(usuario_id, ahora_naive)
    
    fecha_expiracion = ahora_naive + (timedelta(days=30) if es_pro else timedelta(minutes=5))

    # --------------------------------------------------------------------------
    # 4. REGISTRO DE AUDITORÍA Y PREPARACIÓN DE WORKSPACE
    # --------------------------------------------------------------------------
    nueva_ejecucion = Ejecucion(
        id_usuario=usuario_id, 
        id_pipeline=id_pipeline_int,
        estado='procesando', 
        config_aplicada=config_usuario_str
    )
    db.session.add(nueva_ejecucion)
    db.session.commit()

    start_time = datetime.now(timezone.utc)
    
    try:
        # Aislamiento físico de la ejecución en disco para evitar colisiones de assets
        folder_path = os.path.join(CARPETA_EJECUCIONES, f"exec_{nueva_ejecucion.id_ejecucion}")
        os.makedirs(folder_path, exist_ok=True)
        
        prefijo = f"u{usuario_id}_t{int(ahora_utc.timestamp())}"
        filename = secure_filename(f"{prefijo}_{imagen_file.filename}")
        ruta_input = os.path.join(folder_path, filename)
        imagen_file.save(ruta_input)

        # Registro del asset original en la tabla de activos temporales
        db.session.add(TemporalArchivo(
            id_ejecucion=nueva_ejecucion.id_ejecucion, 
            tipo="imagen_original", 
            ruta_servidor=ruta_input, 
            token_descarga=str(uuid.uuid4()), 
            expira_en=fecha_expiracion
        ))

        # --------------------------------------------------------------------------
        # 5. EJECUCIÓN DEL MOTOR DE INFERENCIA (PIPELINE RUNNER)
        # --------------------------------------------------------------------------
        _, analisis = PipelineRunner.ejecutar_pipeline(id_pipeline_int, ruta_input, config_dict, prefijo)
        
        # --------------------------------------------------------------------------
        # 6. OFUSCACIÓN DE RESULTADOS Y PERSISTENCIA DE ARTEFACTOS
        # --------------------------------------------------------------------------
        for etapa in analisis:
            tokens_img = []
            for img_name in etapa["imagenes"]:
                token = str(uuid.uuid4())
                ruta_full = os.path.join(folder_path, img_name)
                
                db.session.add(TemporalArchivo(
                    id_ejecucion=nueva_ejecucion.id_ejecucion, 
                    tipo="resultado_imagen", 
                    ruta_servidor=ruta_full, 
                    token_descarga=token, 
                    expira_en=fecha_expiracion
                ))
                tokens_img.append(token)
            
            # Abstracción de seguridad: El cliente recibe tokens únicos, no rutas del servidor
            etapa["imagenes"] = tokens_img 

            # Persistencia de metadatos de inferencia en formato JSON
            json_name = f"{prefijo}_data_e{etapa['etapa']}.json"
            ruta_json = os.path.join(folder_path, json_name)
            with open(ruta_json, 'w', encoding='utf-8') as f:
                json.dump(etapa["datos"], f, indent=4, ensure_ascii=False)
            
            token_json = str(uuid.uuid4())
            db.session.add(TemporalArchivo(
                id_ejecucion=nueva_ejecucion.id_ejecucion, 
                tipo="resultado_json", 
                ruta_servidor=ruta_json, 
                token_descarga=token_json, 
                expira_en=fecha_expiracion
            ))
            etapa["token_json_descarga"] = token_json

        # Finalización exitosa: Cierre de métricas de rendimiento
        nueva_ejecucion.estado = 'completado'
        nueva_ejecucion.duracion_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        db.session.commit()
        
        return jsonify({"status": "success", "resultados_etapas": analisis}), 200

    except Exception as e:
        # Gestión de fallos críticos: Rollback de transacciones y registro del error
        db.session.rollback()
        nueva_ejecucion.estado = 'error'
        nueva_ejecucion.mensaje_error_user = str(e)
        db.session.commit()
        return jsonify({
            "status": "error", 
            "mensaje": f"Fallo crítico durante el procesamiento: {str(e)}"
        }), 500

# ==============================================================================
# AUDITORÍA Y DISTRIBUCIÓN DE ACTIVOS
# ==============================================================================
@pipeline_bp.route('/outputs/<token>')
def serve_output(token):
    """
    Capa de abstracción segura para la entrega de archivos estáticos.
    Resuelve el token único, valida la política de expiración (TTL) y retorna el asset físico.
    """
    archivo = TemporalArchivo.query.filter_by(token_descarga=token).first()
    ahora_naive = ahora_utc_naive()
    
    if not archivo or (archivo.expira_en and archivo.expira_en <= ahora_naive):
        return jsonify({"error": "Excepción de seguridad: El recurso solicitado ya no está disponible o ha expirado"}), 404
    if not archivo.ruta_servidor or not os.path.exists(archivo.ruta_servidor):
        return jsonify({"error": "Excepción de Integridad: El activo físico ha sido corrompido o purgado del almacenamiento."}), 404
        
    return send_file(archivo.ruta_servidor)

@pipeline_bp.route('/historial', methods=['GET'])
@jwt_required()
def historial_ejecuciones():
    """Retorna el log cronológico de operaciones del usuario autenticado."""
    usuario_id = get_jwt_identity()
    ahora_naive = ahora_utc_naive()

    ejecuciones = Ejecucion.query.filter_by(
        id_usuario=usuario_id
    ).order_by(Ejecucion.creado_en.desc()).all()

    resultado = []

    for ej in ejecuciones:
        pipe = db.session.get(Pipeline, ej.id_pipeline)

        activos = TemporalArchivo.query.filter(
            TemporalArchivo.id_ejecucion == ej.id_ejecucion,
            TemporalArchivo.expira_en > ahora_naive
        ).first()

        resultado.append({
            "id": ej.id_ejecucion,
            "pipeline": pipe.nombre if pipe else "Instancia Desconocida",
            "fecha": formatear_fecha_local(ej.creado_en),
            "estado": ej.estado,
            "duracion": f"{ej.duracion_ms} ms" if ej.duracion_ms else "-",
            "error": ej.mensaje_error_user,
            "archivos_disponibles": bool(activos),
            "config_aplicada": ej.config_aplicada
        })

    return jsonify(resultado), 200

@pipeline_bp.route('/ejecuciones_totales', methods=['GET'])
@jwt_required()
def ejecuciones_totales_admin():
    """
    Retorna el historial global de ejecuciones para el panel administrativo.
    Solo es accesible por usuarios con rol admin.
    """
    if "admin" not in get_jwt().get("roles", []):
        return jsonify({"mensaje": "Violación de acceso: Privilegios insuficientes"}), 403

    try:
        ejecuciones = Ejecucion.query.order_by(Ejecucion.creado_en.desc()).all()

        resultado = []

        for ej in ejecuciones:
            usuario = db.session.get(Usuario, ej.id_usuario)
            pipeline = db.session.get(Pipeline, ej.id_pipeline)

            resultado.append({
                "id": ej.id_ejecucion,
                "usuario": usuario.username if usuario else "Usuario eliminado",
                "pipeline": pipeline.nombre if pipeline else "Pipeline eliminado",
                "fecha": formatear_fecha_local(ej.creado_en),
                "estado": ej.estado,
                "duracion": f"{ej.duracion_ms} ms" if ej.duracion_ms else "-",
                "error": ej.mensaje_error_user
            })

        return jsonify(resultado), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "mensaje": f"Error al obtener auditoría global: {str(e)}"
        }), 500

@pipeline_bp.route('/ejecucion/<int:id_ejecucion>/archivos', methods=['GET'])
@jwt_required()
def obtener_archivos_ejecucion(id_ejecucion):
    """
    Reconstruye estructuralmente los recursos de una ejecución para su visualización.
    Mapea tokens de descarga con las etapas lógicas correspondientes.
    """
    usuario_id = get_jwt_identity()
    ahora_naive = ahora_utc_naive()

    ejecucion = Ejecucion.query.filter_by(
        id_ejecucion=id_ejecucion,
        id_usuario=usuario_id
    ).first()

    if not ejecucion:
        return jsonify({
            "error": "Violación de acceso: Permiso denegado para esta instancia"
        }), 403

    archivos = TemporalArchivo.query.filter(
        TemporalArchivo.id_ejecucion == id_ejecucion,
        TemporalArchivo.expira_en > ahora_naive
    ).order_by(TemporalArchivo.id_temporal.asc()).all()

    etapas = PipelineEtapa.query.filter_by(
        id_pipeline=ejecucion.id_pipeline
    ).order_by(PipelineEtapa.orden).all()

    datos_etapas = []
    img_list = []
    idx_etapa = 0
    img_orig = None

    for arch in archivos:
        info_archivo = {
            "token": arch.token_descarga,
            "nombre": os.path.basename(arch.ruta_servidor)
        }

        if arch.tipo == "imagen_original":
            img_orig = info_archivo

        elif arch.tipo == "resultado_imagen":
            img_list.append(info_archivo)

        elif arch.tipo == "resultado_json":
            etapa_bd = etapas[idx_etapa] if idx_etapa < len(etapas) else None

            numero_etapa = etapa_bd.orden if etapa_bd else idx_etapa + 1
            nombre_etapa = etapa_bd.nombre if etapa_bd else f"Etapa {numero_etapa}"
            nombre_ia = etapa_bd.modelo.nombre if etapa_bd and etapa_bd.modelo else "N/A"
            nombre_modo = etapa_bd.modo.nombre_modo if etapa_bd and etapa_bd.modo else "N/A"

            datos_etapas.append({
                "info": {
                    "etapa": numero_etapa,
                    "nombre_etapa": nombre_etapa,
                    "ia": nombre_ia,
                    "modo": nombre_modo
                },
                "nombre_etapa": nombre_etapa,
                "imagenes": img_list,
                "json": info_archivo
            })

            img_list = []
            idx_etapa += 1

    return jsonify({
        "imagen_original": img_orig,
        "etapas": datos_etapas
    }), 200