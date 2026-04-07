import os
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from app.services.pipeline_runner import PipelineRunner

# Creamos el Blueprint para modularizar las rutas
pipeline_bp = Blueprint('pipeline', __name__)

# Carpeta temporal para guardar las imágenes subidas (RF-MVP-4.3 y CU-MVP-8)
TEMP_FOLDER = '/tmp/tfg_uploads'
os.makedirs(TEMP_FOLDER, exist_ok=True)

@pipeline_bp.route('/analizar', methods=['POST'])
def analizar_imagen():
    # Validar si viene la imagen y el ID del pipeline
    if 'imagen' not in request.files:
        return jsonify({"error": "No se ha enviado ninguna imagen"}), 400
        
    id_pipeline = request.form.get('id_pipeline')
    if not id_pipeline:
        return jsonify({"error": "No se ha especificado el id_pipeline"}), 400

    imagen_file = request.files['imagen']
    if imagen_file.filename == '':
        return jsonify({"error": "El nombre del archivo está vacío"}), 400

    try:
        # 1. Guardar la imagen temporalmente de forma segura
        filename = secure_filename(imagen_file.filename)
        ruta_temporal = os.path.join(TEMP_FOLDER, filename)
        imagen_file.save(ruta_temporal)
        
        # 2. Llamar al servicio Orquestador (PipelineRunner)
        img_final, analisis = PipelineRunner.ejecutar_pipeline(int(id_pipeline), ruta_temporal)
        
        # 3. Retornar el JSON con los resultados
        return jsonify({
            "status": "success",
            "mensaje": "Pipeline ejecutado correctamente",
            "imagen_resultado": img_final,
            "analisis_completo": analisis
        }), 200
        
    except ValueError as ve:
        # Errores controlados (ej. modo no existe)
        return jsonify({"status": "error", "mensaje": str(ve)}), 400
    except Exception as e:
        # Errores inesperados (RF-MVP-6.4: informar sin excesivos detalles técnicos en un entorno real)
        return jsonify({"status": "error", "mensaje": f"Error interno: {str(e)}"}), 500