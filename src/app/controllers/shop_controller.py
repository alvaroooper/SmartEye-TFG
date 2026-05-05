from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from app import db
from app.models import Pipeline, PipelineEtapa, IAModo, IAModelo, Alquila, SuscripcionPlan, TipoPlan

shop_bp = Blueprint('shop', __name__)

@shop_bp.route('/modelos', methods=['GET'])
@jwt_required()
def list_shop():
    usuario_id = get_jwt_identity()
    
    # 1. Obtenemos solo las IAs habilitadas (habilitada=True / 1)
    modelos_ia = IAModelo.query.filter_by(habilitada=True).all()
    
    # 2. Vemos cuáles tiene ya alquiladas activamente este usuario
    ahora = datetime.now()
    alquileres_activos = Alquila.query.filter(
        Alquila.id_usuario == usuario_id,
        Alquila.activo == 1,
        Alquila.periodo_inicio <= ahora,
        (Alquila.periodo_fin >= ahora) | (Alquila.periodo_fin.is_(None))
    ).all()
    
    ids_alquilados = [a.id_ia for a in alquileres_activos]
    
    datos = []
    for ia in modelos_ia:
        # Precios nulos se tratan como 0.00
        precio_float = float(ia.precio) if ia.precio is not None else 0.00 
        
        datos.append({
            "id_ia": ia.id_ia,
            "nombre": ia.nombre.capitalize(),
            "descripcion": ia.descripcion or "Sin descripción",
            "precio": f"{precio_float} €",
            "alquilado": ia.id_ia in ids_alquilados
        })
        
    return jsonify(datos), 200

@shop_bp.route('/alquilar/<int:id_ia>', methods=['POST'])
@jwt_required()
def rent_model(id_ia):
    usuario_id = get_jwt_identity()
    ahora = datetime.now()
    
    # Recibimos la opción de renovación automática enviada desde el frontend
    datos = request.get_json() or {}
    quiere_renovacion = datos.get('renovacion_auto', False)
    
    # Comprobar si ya tiene un alquiler activo
    existente = Alquila.query.filter(
        Alquila.id_usuario == usuario_id,
        Alquila.id_ia == id_ia,
        Alquila.activo == 1,
        Alquila.periodo_inicio <= ahora,
        (Alquila.periodo_fin >= ahora) | (Alquila.periodo_fin.is_(None))
    ).first()
    
    if existente:
        return jsonify({"status": "error", "mensaje": "Ya tienes esta IA alquilada"}), 400
        
    modelo = IAModelo.query.get(id_ia)
    if not modelo:
        return jsonify({"status": "error", "mensaje": "El modelo no existe"}), 404
        
    try:
        # Si es nulo es 0.00
        precio_alquiler = float(modelo.precio) if modelo.precio is not None else 0.00
        
        nuevo_alquiler = Alquila(
            id_usuario=usuario_id,
            id_ia=id_ia,
            fecha_compra=ahora,
            periodo_inicio=ahora,
            periodo_fin=ahora + timedelta(days=30),
            activo=1, 
            renovacion_auto=1 if quiere_renovacion else 0, # Lo guardamos en BD
            importe=precio_alquiler
        )
        db.session.add(nuevo_alquiler)
        db.session.commit()
        
        return jsonify({"status": "success", "mensaje": f"¡Motor {modelo.nombre} alquilado con éxito!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": f"Error en la transacción: {str(e)}"}), 500
    

@shop_bp.route('/mis_compras', methods=['GET'])
@jwt_required()
def mis_compras():
    usuario_id = get_jwt_identity()
    
    # 1. Obtenemos los alquileres de IA activos
    alquileres = Alquila.query.filter_by(id_usuario=usuario_id, activo=1).all()
    
    datos_alquileres = []
    for a in alquileres:
        ia = IAModelo.query.get(a.id_ia)
        if ia:
            # Formateamos la fecha para que sea legible (ej: 30/05/2026)
            fecha_fin_str = a.periodo_fin.strftime('%d/%m/%Y') if a.periodo_fin else "Indefinido"
            
            datos_alquileres.append({
                "id_compra": a.id_compra,
                "nombre": ia.nombre.capitalize(),
                "fecha_fin": fecha_fin_str,
                "renovacion_auto": True if a.renovacion_auto == 1 else False,
                "importe": str(a.importe)
            })
            
    # 2. ESPACIO PREPARADO PARA EL FUTURO: Suscripciones a Planes

    datos_planes = [] 
            
    return jsonify({
        "status": "success",
        "alquileres": datos_alquileres,
        "planes": datos_planes
    }), 200

@shop_bp.route('/alquiler/<int:id_compra>/toggle_renovacion', methods=['POST'])
@jwt_required()
def toggle_renovacion(id_compra):
    usuario_id = get_jwt_identity()
    
    # Buscamos el alquiler asegurándonos de que pertenece a este usuario por seguridad
    alquiler = Alquila.query.filter_by(id_compra=id_compra, id_usuario=usuario_id).first()
    
    if not alquiler:
        return jsonify({"status": "error", "mensaje": "Alquiler no encontrado o no autorizado"}), 404
        
    # Invertimos el valor: si era 1 pasa a 0, si era 0 pasa a 1
    alquiler.renovacion_auto = 0 if alquiler.renovacion_auto == 1 else 1
    
    try:
        db.session.commit()
        estado_texto = "activada" if alquiler.renovacion_auto == 1 else "desactivada"
        return jsonify({
            "status": "success", 
            "mensaje": f"Renovación automática {estado_texto}",
            "renovacion_auto": True if alquiler.renovacion_auto == 1 else False
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": "Error al actualizar la base de datos"}), 500

@shop_bp.route('/guia_pipelines', methods=['GET'])
@jwt_required()
def guia_pipelines():
    """Devuelve los pipelines públicos y marca qué IAs tiene compradas el usuario"""
    usuario_id = get_jwt_identity()
    ahora = datetime.now()
    
    # 1. Comprobar si el usuario tiene un Plan Pro activo (acceso total a lo público)
    es_pro_activo = SuscripcionPlan.query.join(TipoPlan).filter(
        SuscripcionPlan.id_usuario == usuario_id,
        SuscripcionPlan.activo == 1,
        TipoPlan.nombre == 'Pro',
        SuscripcionPlan.fecha_inicio <= ahora,
        (SuscripcionPlan.fecha_fin >= ahora) | (SuscripcionPlan.fecha_fin.is_(None))
    ).first() is not None

    # 2. Comprobar qué IAs sueltas tiene alquiladas
    alquileres_activos = Alquila.query.filter(
        Alquila.id_usuario == usuario_id,
        Alquila.activo == 1,
        Alquila.periodo_inicio <= ahora,
        (Alquila.periodo_fin >= ahora) | (Alquila.periodo_fin.is_(None))
    ).all()
    ids_ias_alquiladas = {a.id_ia for a in alquileres_activos}

    # 3. Filtrar los pipelines y mapear los estados
    pipelines = Pipeline.query.filter_by(publico=1, habilitado=1).all()
    resultado = []

    for p in pipelines:
        etapas = PipelineEtapa.query.filter_by(id_pipeline=p.id_pipeline).order_by(PipelineEtapa.orden).all()
        
        # Usamos un diccionario para no repetir IAs y guardar su estado (comprada o no)
        ias_requeridas_dict = {} 
        detalles_etapas = []

        for e in etapas:
            ia_obj = IAModelo.query.get(e.id_ia)
            modo_obj = IAModo.query.get(e.id_modo)
            
            if ia_obj and ia_obj.id_ia not in ias_requeridas_dict:
                # Si es Pro, lo marcamos como comprado. Si no, comprobamos su ID en los alquileres
                esta_comprada = True if es_pro_activo else (ia_obj.id_ia in ids_ias_alquiladas)
                
                ias_requeridas_dict[ia_obj.id_ia] = {
                    "nombre": ia_obj.nombre.capitalize(),
                    "comprada": esta_comprada
                }
                
            detalles_etapas.append({
                "orden": e.orden,
                "nombre": e.nombre,
                "ia": ia_obj.nombre.capitalize() if ia_obj else "Desconocida",
                "modo": modo_obj.nombre_modo if modo_obj else "Desconocido"
            })

        resultado.append({
            "id_pipeline": p.id_pipeline,
            "nombre": p.nombre,
            "descripcion": p.descripcion or "Este pipeline realiza un análisis avanzado secuencial.",
            "ias_requeridas": list(ias_requeridas_dict.values()), # Ahora es una lista de diccionarios
            "etapas": detalles_etapas
        })

    return jsonify(resultado), 200