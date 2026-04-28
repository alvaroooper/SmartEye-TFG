import os
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, send_from_directory
from flask_jwt_extended import get_jwt, jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
# Importaciones de lógica de negocio y modelos
from app import db
from app.services.pipeline_runner import PipelineRunner
from app.models import Pipeline, SuscripcionPlan, TipoPlan, Alquila, PipelineEtapa, IAModelo, IAModo, Ejecucion

# Creamos el Blueprint para modularizar las rutas 
pipeline_bp = Blueprint('pipeline', __name__)

# Carpeta temporal para guardar las imágenes (debe ser la misma que usa el Runner) 
TEMP_FOLDER = '/tmp/tfg_uploads'
os.makedirs(TEMP_FOLDER, exist_ok=True)

@pipeline_bp.route('/listado', methods=['GET'])
@jwt_required()
def listar_pipelines():
    try:
        # 1. Identificación del usuario y sus roles
        claims = get_jwt()
        roles = claims.get("roles", [])
        usuario_id = get_jwt_identity() # Obtenemos el ID del usuario desde el token JWT

        # CASO 1: EL ADMINISTRADOR VE TODOS LOS PIPELINES SIN FILTRO ALGUNO
        if "admin" in roles:
            pipelines = Pipeline.query.all()
            return jsonify([{"id": p.id_pipeline, "nombre": p.nombre} for p in pipelines]), 200

        # ---- LÓGICA PARA USUARIOS NORMALES ----
        now = datetime.now()

        # 2. Comprobar si tiene un PLAN PRO ACTIVO y en fecha
        es_pro_activo = SuscripcionPlan.query.join(TipoPlan).filter(
            SuscripcionPlan.id_usuario == usuario_id,
            SuscripcionPlan.activo == 1,
            TipoPlan.nombre == 'Pro',
            SuscripcionPlan.fecha_inicio <= now,
            (SuscripcionPlan.fecha_fin >= now) | (SuscripcionPlan.fecha_fin.is_(None))
        ).first() is not None

        # CASO 2: USUARIO PRO ACTIVO -> Ve todos los públicos
        if es_pro_activo:
            pipelines = Pipeline.query.filter_by(publico=1).all()
            return jsonify([{"id": p.id_pipeline, "nombre": p.nombre} for p in pipelines]), 200

        # CASO 3: USUARIO BÁSICO (O PRO CADUCADO) -> Filtrar por Alquileres
        
        # A) ¿Qué IAs tiene alquiladas y activas AHORA MISMO?
        alquileres_activos = Alquila.query.filter(
            Alquila.id_usuario == usuario_id,
            Alquila.activo == 1,
            Alquila.periodo_inicio <= now,
            (Alquila.periodo_fin >= now) | (Alquila.periodo_fin.is_(None))
        ).all()
        
        # Guardamos los IDs de las IAs alquiladas en un "conjunto" (set) para buscar rápido
        ias_alquiladas = {alquiler.id_ia for alquiler in alquileres_activos}

        # B) Analizar cada pipeline público
        pipelines_publicos = Pipeline.query.filter_by(publico=1).all()
        pipelines_permitidos = []

        for pipeline in pipelines_publicos:
            # Sacamos qué IAs necesita este pipeline consultando sus etapas
            etapas = PipelineEtapa.query.filter_by(id_pipeline=pipeline.id_pipeline).all()
            ias_requeridas = {etapa.id_ia for etapa in etapas}

            # Si el pipeline tiene etapas y el usuario tiene TODAS las IAs requeridas alquiladas
            if ias_requeridas and ias_requeridas.issubset(ias_alquiladas):
                pipelines_permitidos.append(pipeline)

        # Devolvemos solo los que superaron el filtro
        resultado = [{"id": p.id_pipeline, "nombre": p.nombre} for p in pipelines_permitidos]
        return jsonify(resultado), 200

    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Error al listar: {str(e)}"}), 500

@pipeline_bp.route('/detalles_completos', methods=['GET'])
@jwt_required()
def listar_detalles_admin():
    claims = get_jwt()
    # Verificación de rol
    if "admin" not in claims.get("roles", []):
        return jsonify({"mensaje": "No autorizado"}), 403

    try:
        # Obtenemos todos los pipelines de la base de datos
        pipelines = Pipeline.query.all()
        resultado = []

        for p in pipelines:
            # Buscamos las etapas de este pipeline concreto ordenadas
            etapas = PipelineEtapa.query.filter_by(id_pipeline=p.id_pipeline).order_by(PipelineEtapa.orden).all()
            
            info_etapas = []
            for e in etapas:
                # BUSQUEDA DIRECTA POR ID (Más seguro que usar relaciones)
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
        # Imprimimos el error en la terminal para que puedas verlo si vuelve a fallar
        print(f"Error detectado en /detalles_completos: {str(e)}")
        return jsonify({"error": str(e)}), 500
        
@pipeline_bp.route('/analizar', methods=['POST'])
@jwt_required()
def analizar_imagen():
    usuario_id = get_jwt_identity()
    id_pipeline = request.form.get('id_pipeline')
    # Recibimos la configuración editada desde el frontend como un string JSON
    config_usuario_str = request.form.get('config_personalizada') 

    if 'imagen' not in request.files or not id_pipeline:
        return jsonify({"status": "error", "mensaje": "Faltan datos"}), 400

    # 1. Crear el registro de ejecución en la BD
    nueva_ejecucion = Ejecucion(
        id_usuario=usuario_id,
        id_pipeline=id_pipeline,
        estado='procesando',
        config_aplicada=config_usuario_str # Guardamos el JSON que se usó
    )
    db.session.add(nueva_ejecucion)
    db.session.commit()

    start_time = datetime.now()

    try:
        imagen_file = request.files['imagen']
        filename = secure_filename(imagen_file.filename)
        # Creamos una carpeta única para esta ejecución
        folder_ejecucion = os.path.join(TEMP_FOLDER, f"exec_{nueva_ejecucion.id_ejecucion}")
        os.makedirs(folder_ejecucion, exist_ok=True)
        
        ruta_input = os.path.join(folder_ejecucion, filename)
        imagen_file.save(ruta_input)

        # 2. Convertir el string de config en diccionario para el Runner
        config_dict = json.loads(config_usuario_str) if config_usuario_str else {}

        # 3. Ejecutar pasándole la configuración completa
        _, analisis = PipelineRunner.ejecutar_pipeline(int(id_pipeline), ruta_input, config_dict)
        
        # 4. Finalizar registro en BD
        end_time = datetime.now()
        nueva_ejecucion.duracion_ms = int((end_time - start_time).total_seconds() * 1000)
        nueva_ejecucion.estado = 'completado'
        db.session.commit()

        return jsonify({"status": "success", "resultados_etapas": analisis}), 200

    except Exception as e:
        nueva_ejecucion.estado = 'error'
        nueva_ejecucion.mensaje_error_user = str(e)
        db.session.commit()
        return jsonify({"status": "error", "mensaje": str(e)}), 500

# Obtener la configuración completa de un pipeline (todas sus etapas)
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
            
            # Guardamos la config de cada etapa usando su orden como clave
            config_completa[f"etapa_{e.orden}"] = config_etapa
            
        return jsonify(config_completa), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@pipeline_bp.route('/outputs/<filename>')
def serve_output(filename):
    """
    Ruta para servir las imágenes procesadas al navegador desde la carpeta temporal.
    """
    return send_from_directory(TEMP_FOLDER, filename)