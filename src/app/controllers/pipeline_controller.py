import os
from flask import Blueprint, request, jsonify, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

# Importaciones de lógica de negocio y modelos
from app.services.pipeline_runner import PipelineRunner
from app.models import Pipeline  # Importación necesaria para listar [cite: 1]

# Creamos el Blueprint para modularizar las rutas 
pipeline_bp = Blueprint('pipeline', __name__)

# Carpeta temporal para guardar las imágenes (debe ser la misma que usa el Runner) 
TEMP_FOLDER = '/tmp/tfg_uploads'
os.makedirs(TEMP_FOLDER, exist_ok=True)

@pipeline_bp.route('/listado', methods=['GET'])
@jwt_required()
def listar_pipelines():
    """
    Endpoint para obtener todos los pipelines disponibles en la base de datos.
    """
    try:
        # Consultamos todos los pipelines registrados en MariaDB
        pipelines = Pipeline.query.all()
        resultado = []
        for p in pipelines:
            resultado.append({
                "id": p.id_pipeline,
                "nombre": p.nombre
            })
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Error al listar: {str(e)}"}), 500

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
        # 2. Guardar la imagen temporalmente de forma segura [cite: 32]
        filename = secure_filename(imagen_file.filename)
        ruta_temporal = os.path.join(TEMP_FOLDER, filename)
        imagen_file.save(ruta_temporal)
        
        # 3. Llamar al servicio Orquestador (PipelineRunner) [cite: 32, 41]
        img_final_full_path, analisis = PipelineRunner.ejecutar_pipeline(int(id_pipeline), ruta_temporal)
        
        # 4. Extraer solo el nombre del archivo para que el frontend lo solicite vía URL
        nombre_archivo_final = os.path.basename(img_final_full_path)
        
        # 5. Retornar el JSON con los resultados [cite: 33]
        return jsonify({
            "status": "success",
            "mensaje": "Pipeline ejecutado correctamente",
            "imagen_resultado": nombre_archivo_final,
            "analisis_completo": analisis
        }), 200
        
    except ValueError as ve:
        # Errores controlados de lógica de negocio (ej. pipeline inexistente) [cite: 34]
        return jsonify({"status": "error", "mensaje": str(ve)}), 400
    except Exception as e:
        # Errores inesperados del servidor [cite: 34]
        return jsonify({"status": "error", "mensaje": f"Error interno: {str(e)}"}), 500

@pipeline_bp.route('/outputs/<filename>')
def serve_output(filename):
    """
    Ruta para servir las imágenes procesadas al navegador desde la carpeta temporal.
    """
    return send_from_directory(TEMP_FOLDER, filename)