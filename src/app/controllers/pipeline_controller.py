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
@pipeline_bp.before_app_request # <--- IMPORTANTE: Usamos before_app_request para que aplique a TODA la app
def tareas_mantenimiento_automaticas():
    """
    Se ejecuta automáticamente en silencio antes de procesar cualquier petición.
    Sirve como un "Cron Job" simulado para mantener el TFG limpio y gestionar pagos.
    """
    try:
        now = datetime.now()
        cambios_realizados = False
        
        # --- 1. RECOLECTOR DE BASURA (Imágenes y JSON temporales) ---
        archivos_caducados = TemporalArchivo.query.filter(TemporalArchivo.expira_en <= now).all()
        for archivo in archivos_caducados:
            if archivo.ruta_servidor and os.path.exists(archivo.ruta_servidor):
                try:
                    os.remove(archivo.ruta_servidor)
                except Exception:
                    pass
            db.session.delete(archivo)
            cambios_realizados = True
            
        # --- 2. GESTOR DE ALQUILERES DE IA ---
        # Buscamos todos los alquileres que están activos pero su fecha ya caducó
        alquileres_vencidos = Alquila.query.filter(
            Alquila.activo == 1,
            Alquila.periodo_fin <= now
        ).all()
        
        for alquiler in alquileres_vencidos:
            if alquiler.renovacion_auto == 1:
                # SIMULACIÓN DE PAGO: Como tiene renovación automática, le sumamos 30 días
                # (En el mundo real aquí se realizaría una petición a la pasarela de pagos y solo si el pago es exitoso se renovaría)
                alquiler.periodo_inicio = now
                alquiler.periodo_fin = alquiler.periodo_fin + timedelta(days=30)
            else:
                alquiler.activo = 0
            
            cambios_realizados = True
            
        # --- 3. GESTOR DE PLANES ---
        # Igual que con los alquileres, buscamos suscripciones que hayan caducado
        suscripciones_vencidas = SuscripcionPlan.query.filter(
            SuscripcionPlan.activo == 1,
            SuscripcionPlan.fecha_fin <= now
        ).all()
        
        for sub in suscripciones_vencidas:
            if sub.renovacion_auto == 1:
                sub.fecha_inicio = now
                sub.fecha_fin = sub.fecha_fin + timedelta(days=30)
            else:
                sub.activo = 0
            cambios_realizados = True
            
        # Si se han limpiado archivos o renovado cuentas, guarda en base de datos
        if cambios_realizados:
            db.session.commit()
            
    except Exception as e:
        db.session.rollback()
        # Imprimimos el error en la consola del servidor pero NO interrumpimos al usuario
        print(f"[MANTENIMIENTO] Error en las tareas automáticas: {str(e)}")

# --- RUTAS DE LA API ---

@pipeline_bp.route('/listado', methods=['GET'])
@jwt_required()
def listar_pipelines():
    try:
        claims = get_jwt()
        roles = claims.get("roles", [])
        usuario_id = get_jwt_identity()

        # 1. Si es Admin, lo ve todo, pero solo si el pipeline está habilitado
        if "admin" in roles:
            pipelines = Pipeline.query.filter_by(habilitado=1).all()
            return jsonify([{"id": p.id_pipeline, "nombre": p.nombre} for p in pipelines]), 200

        now = datetime.now()
        
        # 2. Comprobación estricta del Plan PRO (Activo = 1 + Fechas correctas)
        es_pro_activo = SuscripcionPlan.query.join(TipoPlan).filter(
            SuscripcionPlan.id_usuario == usuario_id,
            SuscripcionPlan.activo == 1,
            TipoPlan.nombre == 'Pro',
            SuscripcionPlan.fecha_inicio <= now,
            (SuscripcionPlan.fecha_fin >= now) | (SuscripcionPlan.fecha_fin.is_(None))
        ).first() is not None

        if es_pro_activo:
            # Añadido: habilitado=1 para que no salgan los que el admin haya apagado
            pipelines = Pipeline.query.filter_by(publico=1, habilitado=1).all()
            return jsonify([{"id": p.id_pipeline, "nombre": p.nombre} for p in pipelines]), 200

        # 3. Comprobación estricta de ALQUILERES (Activo = 1 + Fechas correctas)
        alquileres_activos = Alquila.query.filter(
            Alquila.id_usuario == usuario_id,
            Alquila.activo == 1,
            Alquila.periodo_inicio <= now,
            (Alquila.periodo_fin >= now) | (Alquila.periodo_fin.is_(None))
        ).all()
        
        ias_alquiladas = {alquiler.id_ia for alquiler in alquileres_activos}
        
        # Añadido: habilitado=1
        pipelines_publicos = Pipeline.query.filter_by(publico=1, habilitado=1).all()
        pipelines_permitidos = []

        for pipeline in pipelines_publicos:
            etapas = PipelineEtapa.query.filter_by(id_pipeline=pipeline.id_pipeline).all()
            ias_requeridas = {etapa.id_ia for etapa in etapas}

            # Si el usuario tiene alquiladas TODAS las IAs que requiere este pipeline, se lo mostramos
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
    ahora = datetime.now() # Capturamos el momento exacto
    
    # Buscamos al usuario para obtener su username
    usuario = Usuario.query.get(usuario_id)
    nombre_user = usuario.username if usuario else "desconocido"
    
    # Generamos la fecha hasta los segundos y creamos el prefijo único
    fecha_str = ahora.strftime("%Y%m%d%H%M%S")
    prefijo = f"{nombre_user}_{fecha_str}"

    id_pipeline = request.form.get('id_pipeline')
    config_usuario_str = request.form.get('config_personalizada') 

    # Validaciones de entrada
    if 'imagen' not in request.files or not id_pipeline:
        return jsonify({"status": "error", "mensaje": "Faltan datos (imagen o id_pipeline)"}), 400
        
    imagen_file = request.files['imagen']
    if imagen_file.filename == '':
        return jsonify({"status": "error", "mensaje": "No se ha seleccionado ninguna imagen"}), 400

    # --- LÓGICA DE RETENCIÓN DE DATOS (PRO vs BÁSICO) ---
    # Comprobamos si el usuario tiene un Plan Pro activo
    es_pro_activo = SuscripcionPlan.query.join(TipoPlan).filter(
        SuscripcionPlan.id_usuario == usuario_id,
        SuscripcionPlan.activo == 1,
        TipoPlan.nombre == 'Pro',
        SuscripcionPlan.fecha_inicio <= ahora,
        (SuscripcionPlan.fecha_fin >= ahora) | (SuscripcionPlan.fecha_fin.is_(None))
    ).first() is not None

    # Si es Pro le damos 7 días, si es básico le damos 5 minutos
    tiempo_retencion = timedelta(days=7) if es_pro_activo else timedelta(minutes=5)
    fecha_expiracion = ahora + tiempo_retencion
    # -----------------------------------------------------------

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

        # REGISTRAR LA IMAGEN ORIGINAL aplicando la fecha de expiración calculada
        token_original = str(uuid.uuid4())
        archivo_original_temp = TemporalArchivo(
            id_ejecucion=nueva_ejecucion.id_ejecucion,
            tipo="imagen_original",
            ruta_servidor=ruta_input,
            token_descarga=token_original,
            expira_en=fecha_expiracion 
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
                    expira_en=fecha_expiracion 
                )
                db.session.add(archivo_temp_img)
                tokens_imagenes.append(token_img)
            
            # Reemplazamos nombres físicos por tokens para el frontend
            etapa["imagenes"] = tokens_imagenes

            # --- Gestión del JSON físico ---
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
                expira_en=fecha_expiracion # 
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

@pipeline_bp.route('/historial', methods=['GET'])
@jwt_required()
def historial_ejecuciones():
    usuario_id = get_jwt_identity()
    now = datetime.now()
    
    ejecuciones = Ejecucion.query.filter_by(id_usuario=usuario_id)\
                                 .order_by(Ejecucion.creado_en.desc())\
                                 .all()
    
    resultado = []
    for ej in ejecuciones:
        pipeline = Pipeline.query.get(ej.id_pipeline)
        nombre_pipe = pipeline.nombre if pipeline else "Pipeline Eliminado"
        fecha_formateada = ej.creado_en.strftime("%d/%m/%Y %H:%M")
        
        # Comprobar si todavía existen archivos vivos para esta ejecución
        archivos_activos = TemporalArchivo.query.filter(
            TemporalArchivo.id_ejecucion == ej.id_ejecucion,
            TemporalArchivo.expira_en > now
        ).first()
        
        resultado.append({
            "id": ej.id_ejecucion,
            "pipeline": nombre_pipe,
            "fecha": fecha_formateada,
            "estado": ej.estado,
            "duracion": f"{ej.duracion_ms} ms" if ej.duracion_ms else "-",
            "error": ej.mensaje_error_user,
            "config_aplicada": ej.config_aplicada,
            "archivos_disponibles": True if archivos_activos else False # <--- NUEVO
        })
        
    return jsonify(resultado), 200

@pipeline_bp.route('/ejecucion/<int:id_ejecucion>/archivos', methods=['GET'])
@jwt_required()
def obtener_archivos_ejecucion(id_ejecucion):
    usuario_id = get_jwt_identity()
    now = datetime.now()
    
    ejecucion = Ejecucion.query.filter_by(id_ejecucion=id_ejecucion, id_usuario=usuario_id).first()
    if not ejecucion:
        return jsonify({"error": "No autorizado"}), 403
        
    archivos = TemporalArchivo.query.filter(
        TemporalArchivo.id_ejecucion == id_ejecucion,
        TemporalArchivo.expira_en > now
    ).order_by(TemporalArchivo.id_temporal).all()
    
    etapas = PipelineEtapa.query.filter_by(id_pipeline=ejecucion.id_pipeline).order_by(PipelineEtapa.orden).all()
    
    datos_etapas = []
    imagen_original = None 
    indice_etapa = 0
    imagenes_etapa_actual = []
    
    for arch in archivos:
        info = {
            "token": arch.token_descarga,
            "nombre": os.path.basename(arch.ruta_servidor) if arch.ruta_servidor else "archivo"
        }
        
        if arch.tipo == "imagen_original":
            imagen_original = info 
        elif arch.tipo == "resultado_imagen":
            imagenes_etapa_actual.append(info)
        elif arch.tipo == "resultado_json":
            # (Lógica de agrupación de etapas)
            if indice_etapa < len(etapas):
                e = etapas[indice_etapa]
                ia_obj = IAModelo.query.get(e.id_ia)
                modo_obj = IAModo.query.get(e.id_modo)
                etapa_info = {
                    "etapa": e.orden, "nombre_etapa": e.nombre,
                    "ia": ia_obj.nombre if ia_obj else "Desconocida",
                    "modo": modo_obj.nombre_modo if modo_obj else "Desconocido"
                }
            else:
                etapa_info = {"etapa": indice_etapa + 1, "nombre_etapa": "Etapa"}
                
            datos_etapas.append({
                "info": etapa_info,
                "imagenes": imagenes_etapa_actual,
                "json": info
            })
            imagenes_etapa_actual = []
            indice_etapa += 1
            
    # Devolvemos también la imagen original en el JSON 
    return jsonify({
        "imagen_original": imagen_original, 
        "etapas": datos_etapas
    }), 200