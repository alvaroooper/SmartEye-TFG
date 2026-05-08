from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from app import db
from app.models import Pipeline, PipelineEtapa, IAModo, IAModelo, Alquila, SuscripcionPlan, TipoPlan

shop_bp = Blueprint('shop', __name__)

# ==============================================================================
# SECCIÓN 1: TIENDA DE MOTORES IA (ALQUILERES)
# ==============================================================================

@shop_bp.route('/modelos', methods=['GET'])
@jwt_required()
def list_shop():
    usuario_id = get_jwt_identity()
    ahora = datetime.now()
    modelos_ia = IAModelo.query.filter_by(habilitada=True).all()
    
    # Buscamos alquileres que estén marcados como activos Y que no hayan caducado
    alquileres = Alquila.query.filter(
        Alquila.id_usuario == usuario_id,
        Alquila.activo == 1,
        (Alquila.periodo_fin >= ahora) | (Alquila.periodo_fin.is_(None))
    ).all()
    
    datos = []
    for ia in modelos_ia:
        precio_float = float(ia.precio) if ia.precio is not None else 0.00 
        alquiler_usuario = next((a for a in alquileres if a.id_ia == ia.id_ia), None)
        estado_alquiler = "disponible"
        
        if alquiler_usuario:
            # Si el inicio es futuro -> Programado. Si ya empezó -> Activo.
            estado_alquiler = "activo" if alquiler_usuario.periodo_inicio <= ahora else "programado"

        datos.append({
            "id_ia": ia.id_ia,
            "nombre": ia.nombre.capitalize(),
            "descripcion": ia.descripcion or "Sin descripción",
            "precio": f"{precio_float} €",
            "estado": estado_alquiler
        })
    return jsonify(datos), 200

@shop_bp.route('/alquilar/<int:id_ia>', methods=['POST'])
@jwt_required()
def rent_model(id_ia):
    """Procesa el alquiler de un motor IA por 30 días, permitiendo elegir fecha de inicio."""
    usuario_id = get_jwt_identity()
    ahora = datetime.now()
    
    datos = request.get_json() or {}
    quiere_renovacion = datos.get('renovacion_auto', False)
    fecha_inicio_str = datos.get('fecha_inicio') 
    
    # Validar y parsear la fecha de inicio personalizada
    if fecha_inicio_str:
        try:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
            if fecha_inicio.date() <= ahora.date():
                fecha_inicio = ahora
        except ValueError:
            fecha_inicio = ahora
    else:
        fecha_inicio = ahora

    # Evitar alquileres duplicados para las mismas fechas
    existente = Alquila.query.filter(
        Alquila.id_usuario == usuario_id,
        Alquila.id_ia == id_ia,
        Alquila.activo == 1,
        (Alquila.periodo_fin >= fecha_inicio) | (Alquila.periodo_fin.is_(None))
    ).first()
    
    if existente:
        return jsonify({"status": "error", "mensaje": "Ya tienes esta IA alquilada para esas fechas"}), 400
        
    modelo = IAModelo.query.get(id_ia)
    if not modelo:
        return jsonify({"status": "error", "mensaje": "El modelo no existe"}), 404
        
    try:
        precio_alquiler = float(modelo.precio) if modelo.precio is not None else 0.00
        
        nuevo_alquiler = Alquila(
            id_usuario=usuario_id,
            id_ia=id_ia,
            fecha_compra=ahora,
            periodo_inicio=fecha_inicio, 
            periodo_fin=fecha_inicio + timedelta(days=30),
            activo=1, 
            renovacion_auto=1 if quiere_renovacion else 0,
            importe=precio_alquiler
        )
        db.session.add(nuevo_alquiler)
        db.session.commit()
        
        return jsonify({"status": "success", "mensaje": f"¡Motor {modelo.nombre} alquilado/programado con éxito!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": f"Error en la BD: {str(e)}"}), 500    


# ==============================================================================
# SECCIÓN 2: TIENDA DE PLANES
# ==============================================================================

@shop_bp.route('/planes', methods=['GET'])
@jwt_required()
def list_planes():
    usuario_id = get_jwt_identity()
    ahora = datetime.now()
    planes = TipoPlan.query.filter_by(habilitado=True).all()
    
    # Solo consideramos "del usuario" las suscripciones que no han expirado
    suscripciones = SuscripcionPlan.query.filter(
        SuscripcionPlan.id_usuario == usuario_id,
        SuscripcionPlan.activo == 1,
        (SuscripcionPlan.fecha_fin >= ahora) | (SuscripcionPlan.fecha_fin.is_(None))
    ).all()
    
    datos = []
    for p in planes:
        precio = float(p.precio_mensual) if p.precio_mensual is not None else 0.00
        sub_usuario = next((s for s in suscripciones if s.id_plan == p.id_plan), None)
        estado = "disponible"
        
        if sub_usuario:
            estado = "activo" if sub_usuario.fecha_inicio <= ahora else "programado"
                
        datos.append({
            "id_plan": p.id_plan,
            "nombre": p.nombre,
            "precio": precio,
            "estado": estado
        })
    return jsonify(datos), 200

@shop_bp.route('/suscribir/<int:id_plan>', methods=['POST'])
@jwt_required()
def suscribir_plan(id_plan):
    """Procesa el cambio de plan, permitiendo programar la fecha de inicio."""
    usuario_id = get_jwt_identity()
    ahora = datetime.now()
    
    datos = request.get_json() or {}
    quiere_renovacion = datos.get('renovacion_auto', False)
    fecha_inicio_str = datos.get('fecha_inicio')
    
    # Validar fecha inicio
    if fecha_inicio_str:
        try:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
            if fecha_inicio.date() <= ahora.date():
                fecha_inicio = ahora
        except ValueError:
            fecha_inicio = ahora
    else:
        fecha_inicio = ahora

    plan = TipoPlan.query.get(id_plan)
    if not plan:
        return jsonify({"status": "error", "mensaje": "Plan no encontrado"}), 404
        
    try:
        # Desactivamos de inmediato cualquier plan anterior
        SuscripcionPlan.query.filter_by(id_usuario=usuario_id, activo=1).update({"activo": 0})
        
        precio = float(plan.precio_mensual) if plan.precio_mensual is not None else 0.00
        
        # Si es gratis, acceso infinito. Si es de pago, 30 días desde la fecha de inicio.
        fecha_fin = None if precio == 0.0 else fecha_inicio + timedelta(days=30)
        
        nueva_sub = SuscripcionPlan(
            id_usuario=usuario_id,
            id_plan=id_plan,
            fecha_compra=ahora,
            fecha_inicio=fecha_inicio, 
            fecha_fin=fecha_fin, 
            activo=1,
            renovacion_auto=1 if quiere_renovacion and precio > 0 else 0,
            importe=precio
        )
        db.session.add(nueva_sub)
        db.session.commit()
        return jsonify({"status": "success", "mensaje": f"¡Suscrito al Plan {plan.nombre} con éxito!"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": str(e)}), 500    


# ==============================================================================
# SECCIÓN 3: GESTIÓN DE COMPRAS ACTIVAS (Renovaciones y Activaciones Rápidas)
# ==============================================================================

@shop_bp.route('/mis_compras', methods=['GET'])
@jwt_required()
def mis_compras():
    """
    Devuelve todo lo que el usuario ha comprado (Planes y Motores IA) unificando formatos
    y filtrando por fecha de expiración.
    """
    usuario_id = get_jwt_identity()
    ahora = datetime.now()
    
    # 1. Alquileres: Filtramos por activo=1 Y que no hayan vencido aún (fecha_fin >= ahora)
    alquileres = Alquila.query.filter(
        Alquila.id_usuario == usuario_id,
        Alquila.activo == 1,
        (Alquila.periodo_fin >= ahora) | (Alquila.periodo_fin.is_(None))
    ).all()
    
    datos_alquileres = []
    for a in alquileres:
        ia = IAModelo.query.get(a.id_ia)
        if ia:
            # Determinamos si ya puede usarlo o si está programado para el futuro
            estado = "activo" if a.periodo_inicio <= ahora else "programado"
            datos_alquileres.append({
                "id_compra": a.id_compra,
                "nombre": ia.nombre.capitalize(),
                "fecha_inicio": a.periodo_inicio.strftime('%d/%m/%Y'),
                "fecha_fin": a.periodo_fin.strftime('%d/%m/%Y') if a.periodo_fin else "Para siempre",
                "estado": estado,
                "renovacion_auto": True if a.renovacion_auto == 1 else False,
                "importe": str(a.importe)
            })
            
    # 2. Planes: Filtramos por activo=1 Y que no hayan vencido aún (fecha_fin >= ahora)
    suscripciones = SuscripcionPlan.query.filter(
        SuscripcionPlan.id_usuario == usuario_id,
        SuscripcionPlan.activo == 1,
        (SuscripcionPlan.fecha_fin >= ahora) | (SuscripcionPlan.fecha_fin.is_(None))
    ).all()
    
    datos_planes = []
    for sub in suscripciones:
        plan = TipoPlan.query.get(sub.id_plan)
        if plan:
            # Determinamos si ya puede usarlo o si está programado para el futuro
            estado = "activo" if sub.fecha_inicio <= ahora else "programado"
            precio_float = float(sub.importe) if sub.importe is not None else 0.00
            datos_planes.append({
                "id_suscripcion": sub.id_suscripcion,
                "nombre": plan.nombre,
                "fecha_inicio": sub.fecha_inicio.strftime('%d/%m/%Y'),
                "fecha_fin": sub.fecha_fin.strftime('%d/%m/%Y') if sub.fecha_fin else "Para siempre",
                "estado": estado,
                "renovacion_auto": True if sub.renovacion_auto == 1 else False,
                "importe": str(precio_float),
                "es_gratis": precio_float == 0.00
            })
            
    return jsonify({"status": "success", "alquileres": datos_alquileres, "planes": datos_planes}), 200

@shop_bp.route('/alquiler/<int:id_compra>/toggle_renovacion', methods=['POST'])
@jwt_required()
def toggle_renovacion_alquiler(id_compra):
    usuario_id = get_jwt_identity()
    alquiler = Alquila.query.filter_by(id_compra=id_compra, id_usuario=usuario_id).first()
    
    if not alquiler: return jsonify({"status": "error", "mensaje": "Alquiler no encontrado"}), 404
        
    alquiler.renovacion_auto = 0 if alquiler.renovacion_auto == 1 else 1
    db.session.commit()
    
    estado_texto = "activada" if alquiler.renovacion_auto == 1 else "desactivada"
    return jsonify({"status": "success", "mensaje": f"Renovación automática {estado_texto}"}), 200


@shop_bp.route('/plan/<int:id_suscripcion>/toggle_renovacion', methods=['POST'])
@jwt_required()
def toggle_renovacion_plan(id_suscripcion):
    usuario_id = get_jwt_identity()
    sub = SuscripcionPlan.query.filter_by(id_suscripcion=id_suscripcion, id_usuario=usuario_id).first()
    
    if not sub: return jsonify({"status": "error", "mensaje": "Suscripción no encontrada"}), 404
        
    sub.renovacion_auto = 0 if sub.renovacion_auto == 1 else 1
    db.session.commit()
    return jsonify({"status": "success", "mensaje": "Renovación de plan actualizada"}), 200


@shop_bp.route('/alquiler/<int:id_compra>/empezar_ahora', methods=['POST'])
@jwt_required()
def empezar_ahora_alquiler(id_compra):
    """Fuerza la activación de un alquiler programado para este instante."""
    usuario_id = get_jwt_identity()
    alquiler = Alquila.query.filter_by(id_compra=id_compra, id_usuario=usuario_id).first()
    
    if not alquiler: return jsonify({"status": "error", "mensaje": "No encontrado"}), 404
    
    ahora = datetime.now()
    alquiler.periodo_inicio = ahora
    alquiler.periodo_fin = ahora + timedelta(days=30)
    db.session.commit()
    return jsonify({"status": "success", "mensaje": "¡Alquiler activado! Ya puedes usarlo."}), 200


@shop_bp.route('/plan/<int:id_suscripcion>/empezar_ahora', methods=['POST'])
@jwt_required()
def empezar_ahora_plan(id_suscripcion):
    """Fuerza la activación de un plan programado para este instante."""
    usuario_id = get_jwt_identity()
    sub = SuscripcionPlan.query.filter_by(id_suscripcion=id_suscripcion, id_usuario=usuario_id).first()
    
    if not sub: return jsonify({"status": "error", "mensaje": "No encontrado"}), 404
    
    ahora = datetime.now()
    sub.fecha_inicio = ahora
    if sub.fecha_fin: 
        sub.fecha_fin = ahora + timedelta(days=30)
    db.session.commit()
    return jsonify({"status": "success", "mensaje": "¡Plan activado! Ya puedes usarlo."}), 200


# ==============================================================================
# SECCIÓN 4: GUÍA DE PIPELINES
# ==============================================================================

@shop_bp.route('/guia_pipelines', methods=['GET'])
@jwt_required()
def guia_pipelines():
    """Devuelve los pipelines públicos evaluando si el usuario actual tiene las IAs necesarias para ejecutarlos."""
    usuario_id = get_jwt_identity()
    ahora = datetime.now()
    
    # Comprobar si es PRO
    es_pro_activo = SuscripcionPlan.query.join(TipoPlan).filter(
        SuscripcionPlan.id_usuario == usuario_id,
        SuscripcionPlan.activo == 1,
        TipoPlan.nombre == 'Pro',
        SuscripcionPlan.fecha_inicio <= ahora,
        (SuscripcionPlan.fecha_fin >= ahora) | (SuscripcionPlan.fecha_fin.is_(None))
    ).first() is not None

    # Recoger IAs alquiladas de forma individual
    alquileres_activos = Alquila.query.filter(
        Alquila.id_usuario == usuario_id,
        Alquila.activo == 1,
        Alquila.periodo_inicio <= ahora,
        (Alquila.periodo_fin >= ahora) | (Alquila.periodo_fin.is_(None))
    ).all()
    ids_ias_alquiladas = {a.id_ia for a in alquileres_activos}

    pipelines = Pipeline.query.filter_by(publico=1, habilitado=1).all()
    resultado = []

    for p in pipelines:
        etapas = PipelineEtapa.query.filter_by(id_pipeline=p.id_pipeline).order_by(PipelineEtapa.orden).all()
        
        ias_requeridas_dict = {} 
        detalles_etapas = []

        for e in etapas:
            ia_obj = IAModelo.query.get(e.id_ia)
            modo_obj = IAModo.query.get(e.id_modo)
            
            if ia_obj and ia_obj.id_ia not in ias_requeridas_dict:
                # Se considera "comprada" si el usuario es Pro o tiene la IA específica alquilada y activa
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
            "ias_requeridas": list(ias_requeridas_dict.values()),
            "etapas": detalles_etapas
        })

    return jsonify(resultado), 200