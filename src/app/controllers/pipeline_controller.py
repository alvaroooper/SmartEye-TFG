import os
import json
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import get_jwt, jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

# Importaciones de tu app
from app import db
from app.services.pipeline_runner import PipelineRunner
from app.models import Pipeline, Usuario, SuscripcionPlan, TipoPlan, Alquila, PipelineEtapa, IAModelo, IAModo, Ejecucion, TemporalArchivo

pipeline_bp = Blueprint('pipeline', __name__)

TEMP_FOLDER = '/tmp/tfg_uploads'
os.makedirs(TEMP_FOLDER, exist_ok=True)

# --- 1. RECOLECTOR DE BASURA AUTOMÁTICO ---
@pipeline_bp.before_request
def limpiar_archivos_caducados():
    """
    Se ejecuta automáticamente antes de procesar cualquier petición.
    Busca los archivos caducados en la BD, borra el archivo físico y elimina el registro.
    """
    try:
        now = datetime.now()
        archivos_caducados = TemporalArchivo.query.filter(TemporalArchivo.expira_en <= now).all()
        
        for archivo in archivos_caducados:
            # Si el archivo físico existe, lo borramos
            if archivo.ruta_servidor and os.path.exists(archivo.ruta_servidor):
                try:
                    os.remove(archivo.ruta_servidor)
                except Exception as e:
                    print(f"No se pudo borrar archivo físico {archivo.ruta_servidor}: {e}")
            
            # Borramos el registro de la base de datos
            db.session.delete(archivo)
            
        if archivos_caducados:
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error en el recolector de basura: {e}")

# --- RUTAS DE LA API ---

@pipeline_bp.route('/listado', methods=['GET'])
@jwt_required()
def listar_pipelines():
    # ... (Mismo código que tenías para listar pipelines) ...
    try:
        claims = get_jwt()
        roles = claims.get("roles", [])
        usuario_id = get_jwt_identity()

        if "admin" in roles:
            pipelines = Pipeline.query.all()
            return jsonify([{"id": p.id_pipeline, "nombre": p.nombre} for p in pipelines]), 200

        now = datetime.now()
        es_pro_activo = SuscripcionPlan.query.join(TipoPlan).filter(
            SuscripcionPlan.id_usuario == usuario_id,
            SuscripcionPlan.activo == 1,
            TipoPlan.nombre == 'Pro',
            SuscripcionPlan.fecha_inicio <= now,
            (SuscripcionPlan.fecha_fin >= now) | (SuscripcionPlan.fecha_fin.is_(None))
        ).first() is not None

        if es_pro_activo:
            pipelines = Pipeline.query.filter_by(publico=1).all()
            return jsonify([{"id": p.id_pipeline, "nombre": p.nombre} for p in pipelines]), 200

        alquileres_activos = Alquila.query.filter(
            Alquila.id_usuario == usuario_id,
            Alquila.activo == 1,
            Alquila.periodo_inicio <= now,
            (Alquila.periodo_fin >= now) | (Alquila.periodo_fin.is_(None))
        ).all()
        
        ias_alquiladas = {alquiler.id_ia for alquiler in alquileres_activos}
        pipelines_publicos = Pipeline.query.filter_by(publico=1).all()
        pipelines_permitidos = []

        for pipeline in pipelines_publicos:
            etapas = PipelineEtapa.query.filter_by(id_pipeline=pipeline.id_pipeline).all()
            ias_requeridas = {etapa.id_ia for etapa in etapas}

            if ias_requeridas and ias_requeridas.issubset(ias_alquiladas):
                pipelines_permitidos.append(pipeline)

        resultado = [{"id": p.id_pipeline, "nombre": p.nombre} for p in pipelines_permitidos]
        return jsonify(resultado), 200

    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Error al listar: {str(e)}"}), 500

@pipeline_bp.route('/configuracion_pipeline/<int:id_pipeline>', methods=['GET'])
@jwt_required()
def obtener_configuracion_completa(id_pipeline):
    try:
        etapas = PipelineEtapa.query.filter_by(id_pipeline=id_pipeline).order_by(PipelineEtapa.orden).all()
        config_completa = {}

        for e in etapas:
            modo = IAModo.query.get(e.id_modo)
            config_etapa = {}
            if modo.config_predeterminada and os.path.exists(modo.config_predeterminada):
                with open(modo.config_predeterminada, 'r') as f:
                    config_etapa = json.load(f)
            
            config_completa[f"etapa_{e.orden}"] = config_etapa
            
        return jsonify(config_completa), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@pipeline_bp.route('/detalles_completos', methods=['GET'])
@jwt_required()
def listar_detalles_admin():
    # ... (Mismo código de detalles_completos sin modificar) ...
    claims = get_jwt()
    if "admin" not in claims.get("roles", []):
        return jsonify({"mensaje": "No autorizado"}), 403

    try:
        pipelines = Pipeline.query.all()
        resultado = []

        for p in pipelines:
            etapas = PipelineEtapa.query.filter_by(id_pipeline=p.id_pipeline).order_by(PipelineEtapa.orden).all()
            info_etapas = []
            for e in etapas:
                ia_obj = IAModelo.query.get(e.id_ia)
                modo_obj = IAModo.query.get(e.id_modo)
                info_etapas.append({
                    "orden": e.orden,
                    "nombre_etapa": e.nombre,
                    "ia": ia_obj.nombre if ia_obj else "IA Desconocida",
                    "modo": modo_obj.nombre_modo if modo_obj else "Modo Desconocido"
                })

            resultado.append({
                "id": p.id_pipeline,
                "nombre": p.nombre,
                "publico": p.publico,
                "descripcion": p.descripcion,
                "etapas": info_etapas
            })
        
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@pipeline_bp.route('/analizar', methods=['POST'])
@jwt_required()
def analizar_imagen():
    usuario_id = get_jwt_identity()
    
    # Buscamos al usuario para obtener su username
    usuario = Usuario.query.get(usuario_id)
    nombre_user = usuario.username if usuario else "desconocido"
    
    # Generamos la fecha hasta los segundos y creamos el prefijo único
    fecha_str = datetime.now().strftime("%Y%m%d%H%M%S")
    prefijo = f"{nombre_user}_{fecha_str}"

    id_pipeline = request.form.get('id_pipeline')
    config_usuario_str = request.form.get('config_personalizada') 

    # Validaciones de entrada
    if 'imagen' not in request.files or not id_pipeline:
        return jsonify({"status": "error", "mensaje": "Faltan datos (imagen o id_pipeline)"}), 400
        
    imagen_file = request.files['imagen']
    if imagen_file.filename == '':
        return jsonify({"status": "error", "mensaje": "No se ha seleccionado ninguna imagen"}), 400

    # 1. Crear el registro de ejecución en la base de datos
    nueva_ejecucion = Ejecucion(
        id_usuario=usuario_id,
        id_pipeline=id_pipeline,
        estado='procesando',
        config_aplicada=config_usuario_str
    )
    db.session.add(nueva_ejecucion)
    db.session.commit()

    start_time = datetime.now()

    try:
        # Preparar carpeta de la ejecución
        folder_ejecucion = os.path.join(TEMP_FOLDER, f"exec_{nueva_ejecucion.id_ejecucion}")
        os.makedirs(folder_ejecucion, exist_ok=True)
        
        # Guardar la imagen original con el prefijo
        filename_orig = secure_filename(f"{prefijo}_{imagen_file.filename}")
        ruta_input = os.path.join(folder_ejecucion, filename_orig)
        imagen_file.save(ruta_input)

        # REGISTRAR LA IMAGEN ORIGINAL para que el recolector de basura la borre
        token_original = str(uuid.uuid4())
        archivo_original_temp = TemporalArchivo(
            id_ejecucion=nueva_ejecucion.id_ejecucion,
            tipo="imagen_original",
            ruta_servidor=ruta_input,
            token_descarga=token_original,
            expira_en=datetime.now() + timedelta(minutes=5)
        )
        db.session.add(archivo_original_temp)

        # Parsear la configuración personalizada del usuario
        config_dict = json.loads(config_usuario_str) if config_usuario_str else {}

        # 2. EJECUTAR EL PIPELINE
        _, analisis = PipelineRunner.ejecutar_pipeline(int(id_pipeline), ruta_input, config_dict, prefijo)
        
        # 3. PROCESAR RESULTADOS (Tokenización y guardado de archivos)
        for etapa in analisis:
            
            # --- Gestión de IMÁGENES resultantes ---
            tokens_imagenes = []
            for img_basename in etapa["imagenes"]:
                token_img = str(uuid.uuid4())
                ruta_completa_img = os.path.join(folder_ejecucion, img_basename)
                
                archivo_temp_img = TemporalArchivo(
                    id_ejecucion=nueva_ejecucion.id_ejecucion,
                    tipo="resultado_imagen",
                    ruta_servidor=ruta_completa_img,
                    token_descarga=token_img,
                    expira_en=datetime.now() + timedelta(minutes=5)
                )
                db.session.add(archivo_temp_img)
                tokens_imagenes.append(token_img)
            
            # Reemplazamos nombres físicos por tokens para el frontend
            etapa["imagenes"] = tokens_imagenes

            # --- Gestión del JSON físico ---
            # Nombre: usuario_fecha_datos_etapa_X_modo.json
            nombre_archivo_json = f"{prefijo}_datos_etapa_{etapa['etapa']}_{etapa['modo']}.json"
            ruta_json_completa = os.path.join(folder_ejecucion, nombre_archivo_json)
            
            # Escribir el JSON en el disco
            with open(ruta_json_completa, 'w', encoding='utf-8') as f:
                json.dump(etapa["datos"], f, indent=4, ensure_ascii=False)
                
            # Registrar el archivo JSON en la base de datos con su token
            token_json = str(uuid.uuid4())
            archivo_temp_json = TemporalArchivo(
                id_ejecucion=nueva_ejecucion.id_ejecucion,
                tipo="resultado_json",
                ruta_servidor=ruta_json_completa,
                token_descarga=token_json,
                expira_en=datetime.now() + timedelta(minutes=5)
            )
            db.session.add(archivo_temp_json)
            
            # Enviamos el token del JSON al frontend para la descarga
            etapa["token_json_descarga"] = token_json

        # 4. Finalizar registro de ejecución con éxito
        end_time = datetime.now()
        nueva_ejecucion.duracion_ms = int((end_time - start_time).total_seconds() * 1000)
        nueva_ejecucion.estado = 'completado'
        db.session.commit()

        return jsonify({"status": "success", "resultados_etapas": analisis}), 200

    except Exception as e:
        db.session.rollback()
        nueva_ejecucion.estado = 'error'
        nueva_ejecucion.mensaje_error_user = str(e)
        db.session.commit()
        return jsonify({"status": "error", "mensaje": str(e)}), 500
        
# --- 4. DESCARGA MEDIANTE TOKEN ---
@pipeline_bp.route('/outputs/<token>')
def serve_output(token):
    """
    Sirve los archivos buscando su ruta real en la BD usando el token de descarga.
    """
    archivo = TemporalArchivo.query.filter_by(token_descarga=token).first()
    
    # Validaciones de seguridad
    if not archivo:
        return jsonify({"error": "Archivo no encontrado o token inválido"}), 404
        
    if archivo.expira_en and archivo.expira_en <= datetime.now():
        return jsonify({"error": "El archivo ha expirado y fue eliminado"}), 410

    if not os.path.exists(archivo.ruta_servidor):
        return jsonify({"error": "Archivo físico no encontrado en el servidor"}), 404

    # Enviamos el archivo real desde su ruta absoluta
    return send_file(archivo.ruta_servidor)