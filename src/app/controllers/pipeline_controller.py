import os
from datetime import datetime
from flask import Blueprint, request, jsonify, send_from_directory
from flask_jwt_extended import get_jwt, jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
# Importaciones de lógica de negocio y modelos
from app.services.pipeline_runner import PipelineRunner
from app.models import Pipeline, SuscripcionPlan, TipoPlan, Alquila, PipelineEtapa, IAModelo, IAModo

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
@jwt_required()  # Requiere que el usuario esté autenticado con JWT 
def analizar_imagen():
    """
    Recibe imagen e ID de pipeline, ejecuta la secuencia de IA y retorna resultados.
    """
    usuario_id = get_jwt_identity()
    print(f"El usuario con ID {usuario_id} está ejecutando la IA.")
    
    # 1. Validaciones de entrada
    if 'imagen' not in request.files:
        return jsonify({"status": "error", "mensaje": "No se ha enviado ninguna imagen"}), 400
        
    id_pipeline = request.form.get('id_pipeline')
    if not id_pipeline:
        return jsonify({"status": "error", "mensaje": "No se ha especificado el id_pipeline"}), 400

    imagen_file = request.files['imagen']
    if imagen_file.filename == '':
        return jsonify({"status": "error", "mensaje": "El nombre del archivo está vacío"}), 400

    try:
        # 2. Guardar la imagen temporalmente de forma segura
        filename = secure_filename(imagen_file.filename)
        ruta_temporal = os.path.join(TEMP_FOLDER, filename)
        imagen_file.save(ruta_temporal)
        
        # 3. Llamar al servicio Orquestador (PipelineRunner)
        img_final_full_path, analisis = PipelineRunner.ejecutar_pipeline(int(id_pipeline), ruta_temporal)
        
        # 4. Extraer solo el nombre del archivo para que el frontend lo solicite vía URL
        nombre_archivo_final = os.path.basename(img_final_full_path)
        
        # 5. Retornar el JSON con los resultados
        return jsonify({
            "status": "success",
            "mensaje": "Pipeline ejecutado correctamente",
            "imagen_resultado": nombre_archivo_final,
            "analisis_completo": analisis
        }), 200
        
    except ValueError as ve:
        # Errores controlados de lógica de negocio (ej. pipeline inexistente)
        return jsonify({"status": "error", "mensaje": str(ve)}), 400
    except Exception as e:
        # Errores inesperados del servidor
        return jsonify({"status": "error", "mensaje": f"Error interno: {str(e)}"}), 500

@pipeline_bp.route('/outputs/<filename>')
def serve_output(filename):
    """
    Ruta para servir las imágenes procesadas al navegador desde la carpeta temporal.
    """
    return send_from_directory(TEMP_FOLDER, filename)