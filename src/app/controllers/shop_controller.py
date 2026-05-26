from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from app.utils.fechas import ahora_utc_naive, formatear_fecha_local
from app import db
from app.models import Pipeline, PipelineEtapa, IAModo, IAModelo, Alquila, SuscripcionPlan, TipoPlan

shop_bp = Blueprint('shop', __name__)

# ==============================================================================
# MÓDULO 1: CATÁLOGO DE MOTORES DE INFERENCIA (LICENCIAS TEMPORALES)
# ==============================================================================

@shop_bp.route('/modelos', methods=['GET'])
@jwt_required()
def list_shop():
    """
    Recupera el catálogo de motores de IA disponibles en la plataforma.
    Cruza la información con el estado contractual del usuario para determinar 
    la disponibilidad mediante una auditoría temporal.
    """
    try:
        usuario_id = get_jwt_identity()
        ahora_naive = ahora_utc_naive()
        
        # Uso de db.session.query para compatibilidad con SQLAlchemy 2.0
        modelos_ia = db.session.query(IAModelo).filter_by(habilitada=True).all()
        
        alquileres = db.session.query(Alquila).filter(
            Alquila.id_usuario == usuario_id,
            Alquila.activo == 1,
            (Alquila.periodo_fin >= ahora_naive) | (Alquila.periodo_fin.is_(None))
        ).all()
        
        datos = []
        for ia in modelos_ia:
            precio_float = float(ia.precio) if ia.precio is not None else 0.00 
            alquiler_usuario = next((a for a in alquileres if a.id_ia == ia.id_ia), None)
            estado_licencia = "disponible"
            
            if alquiler_usuario:
                estado_licencia = "activo" if alquiler_usuario.periodo_inicio <= ahora_naive else "programado"

            datos.append({
                "id_ia": ia.id_ia,
                "nombre": ia.nombre.capitalize(),
                "descripcion": ia.descripcion or "Metadatos no disponibles",
                "precio": f"{precio_float} €",
                "estado": estado_licencia
            })
        return jsonify(datos), 200
    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Error al recuperar el catálogo: {str(e)}"}), 500

@shop_bp.route('/alquilar/<int:id_ia>', methods=['POST'])
@jwt_required()
def rent_model(id_ia):
    """
    Procesa el aprovisionamiento de una licencia de uso temporal (30 días).
    Implementa validación de solapamiento contractual y sanitización de fechas.
    """
    usuario_id = get_jwt_identity()
    ahora_naive = ahora_utc_naive()
    
    datos = request.get_json() or {}
    quiere_renovacion = datos.get('renovacion_auto', False)
    fecha_inicio_str = datos.get('fecha_inicio') 
    
    if fecha_inicio_str:
        try:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
            if fecha_inicio.date() <= ahora_naive.date():
                fecha_inicio = ahora_naive
        except ValueError:
            fecha_inicio = ahora_naive
    else:
        fecha_inicio = ahora_naive

    try:
        # Prevención de colisiones: Evita solapamiento de licencias
        existente = db.session.query(Alquila).filter(
            Alquila.id_usuario == usuario_id,
            Alquila.id_ia == id_ia,
            Alquila.activo == 1,
            (Alquila.periodo_fin >= fecha_inicio) | (Alquila.periodo_fin.is_(None))
        ).first()
        
        if existente:
            return jsonify({"status": "error", "mensaje": "Conflicto de licencia: Activo ya contratado en este periodo."}), 400
            
        modelo = db.session.get(IAModelo, id_ia)
        if not modelo:
            return jsonify({"status": "error", "mensaje": "Motor de IA no localizado en el catálogo."}), 404
            
        precio_alquiler = float(modelo.precio) if modelo.precio is not None else 0.00
        
        nuevo_alquiler = Alquila(
            id_usuario=usuario_id,
            id_ia=id_ia,
            fecha_compra=ahora_naive,
            periodo_inicio=fecha_inicio, 
            periodo_fin=fecha_inicio + timedelta(days=30),
            activo=1, 
            renovacion_auto=1 if quiere_renovacion else 0,
            importe=precio_alquiler
        )
        db.session.add(nuevo_alquiler)
        db.session.commit()
        
        return jsonify({"status": "success", "mensaje": f"Licencia para '{modelo.nombre}' aprovisionada correctamente."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": f"Fallo de persistencia transaccional: {str(e)}"}), 500    

# ==============================================================================
# MÓDULO 2: NIVELES DE SERVICIO (PLANES DE SUSCRIPCIÓN)
# ==============================================================================

@shop_bp.route('/planes', methods=['GET'])
@jwt_required()
def list_planes():
    """Retorna la matriz de niveles de servicio (Tiers) y la vinculación actual del usuario."""
    try:
        usuario_id = get_jwt_identity()
        ahora_naive = ahora_utc_naive()
        planes = db.session.query(TipoPlan).filter_by(habilitado=True).all()
        
        suscripciones = db.session.query(SuscripcionPlan).filter(
            SuscripcionPlan.id_usuario == usuario_id,
            SuscripcionPlan.activo == 1,
            (SuscripcionPlan.fecha_fin >= ahora_naive) | (SuscripcionPlan.fecha_fin.is_(None))
        ).all()
        
        datos = []
        for p in planes:
            precio = float(p.precio_mensual) if p.precio_mensual is not None else 0.00
            sub_usuario = next((s for s in suscripciones if s.id_plan == p.id_plan), None)
            estado = "disponible"
            
            if sub_usuario:
                estado = "activo" if sub_usuario.fecha_inicio <= ahora_naive else "programado"
                    
            datos.append({
                "id_plan": p.id_plan,
                "nombre": p.nombre,
                "precio": precio,
                "estado": estado
            })
        return jsonify(datos), 200
    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Error al consultar planes: {str(e)}"}), 500

@shop_bp.route('/suscribir/<int:id_plan>', methods=['POST'])
@jwt_required()
def suscribir_plan(id_plan):
    """
    Gestión de transiciones de nivel de servicio (Upgrade/Downgrade).
    Revoca automáticamente planes previos para mantener la consistencia (Suscripción Única).
    """
    usuario_id = get_jwt_identity()
    ahora_naive = ahora_utc_naive()
    
    datos = request.get_json() or {}
    quiere_renovacion = datos.get('renovacion_auto', False)
    fecha_inicio_str = datos.get('fecha_inicio')
    
    if fecha_inicio_str:
        try:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
            if fecha_inicio.date() <= ahora_naive.date():
                fecha_inicio = ahora_naive
        except ValueError:
            fecha_inicio = ahora_naive
    else:
        fecha_inicio = ahora_naive

    try:
        plan = db.session.get(TipoPlan, id_plan)
        if not plan:
            return jsonify({"status": "error", "mensaje": "Nivel de servicio no localizado."}), 404
            
        # Revocación lógica: Garantiza un único Tier activo por identidad
        db.session.query(SuscripcionPlan).filter_by(id_usuario=usuario_id, activo=1).update({"activo": 0})
        
        precio = float(plan.precio_mensual) if plan.precio_mensual is not None else 0.00
        fecha_fin = None if precio <= 0.0 else fecha_inicio + timedelta(days=30)
        
        nueva_sub = SuscripcionPlan(
            id_usuario=usuario_id,
            id_plan=id_plan,
            fecha_compra=ahora_naive,
            fecha_inicio=fecha_inicio, 
            fecha_fin=fecha_fin, 
            activo=1,
            renovacion_auto=1 if quiere_renovacion and precio > 0 else 0,
            importe=precio
        )
        db.session.add(nueva_sub)
        db.session.commit()
        return jsonify({"status": "success", "mensaje": f"Transición completada. Nivel actual: {plan.nombre}"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": f"Error transaccional: {str(e)}"}), 500    

# ==============================================================================
# MÓDULO 3: AUDITORÍA DE ACTIVOS Y POLÍTICAS DE RENOVACIÓN
# ==============================================================================

@shop_bp.route('/mis_compras', methods=['GET'])
@jwt_required()
def mis_compras():
    """Consolida todos los activos lógicos (suscripciones y licencias) vinculados a la identidad."""
    DATE_FORMAT = "%d/%m/%Y"
    try:
        usuario_id = get_jwt_identity()
        ahora_naive = ahora_utc_naive()

        alquileres = db.session.query(Alquila).filter(
            Alquila.id_usuario == usuario_id,
            Alquila.activo == 1,
            (Alquila.periodo_fin >= ahora_naive) | (Alquila.periodo_fin.is_(None))
        ).all()

        def map_alquiler(a):
            ia = db.session.get(IAModelo, a.id_ia)
            if not ia:
                return None
            estado = "activo" if a.periodo_inicio <= ahora_naive else "programado"
            return {
                "id_compra": a.id_compra,
                "nombre": ia.nombre.capitalize(),
                "fecha_inicio": formatear_fecha_local(a.periodo_inicio, DATE_FORMAT),
                "fecha_fin": formatear_fecha_local(a.periodo_fin, DATE_FORMAT, "Vitalicio"),
                "estado": estado,
                "renovacion_auto": True if a.renovacion_auto == 1 else False,
                "importe": str(a.importe)
            }

        datos_alquileres = [x for x in (map_alquiler(a) for a in alquileres) if x]

        suscripciones = db.session.query(SuscripcionPlan).filter(
            SuscripcionPlan.id_usuario == usuario_id,
            SuscripcionPlan.activo == 1,
            (SuscripcionPlan.fecha_fin >= ahora_naive) | (SuscripcionPlan.fecha_fin.is_(None))
        ).all()

        def map_suscripcion(sub):
            plan = db.session.get(TipoPlan, sub.id_plan)
            if not plan:
                return None
            estado = "activo" if sub.fecha_inicio <= ahora_naive else "programado"
            precio_float = float(sub.importe) if sub.importe is not None else 0.00
            return {
                "id_suscripcion": sub.id_suscripcion,
                "nombre": plan.nombre,
                "fecha_inicio": formatear_fecha_local(sub.fecha_inicio, DATE_FORMAT),
                "fecha_fin": formatear_fecha_local(sub.fecha_fin, DATE_FORMAT, "Vitalicio"),
                "estado": estado,
                "renovacion_auto": True if sub.renovacion_auto == 1 else False,
                "importe": str(precio_float),
                "es_gratis": precio_float <= 0.00
            }

        datos_planes = [x for x in (map_suscripcion(s) for s in suscripciones) if x]

        return jsonify({"status": "success", "alquileres": datos_alquileres, "planes": datos_planes}), 200
    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Fallo al recuperar activos: {str(e)}"}), 500

@shop_bp.route('/alquiler/<int:id_compra>/toggle_renovacion', methods=['POST'])
@jwt_required()
def toggle_renovacion_alquiler(id_compra):
    """Alterna la política de renovación automática de una licencia de IA."""
    try:
        usuario_id = get_jwt_identity()
        alquiler = db.session.query(Alquila).filter_by(id_compra=id_compra, id_usuario=usuario_id).first()
        
        if not alquiler: return jsonify({"status": "error", "mensaje": "Licencia no localizada"}), 404
            
        alquiler.renovacion_auto = 0 if alquiler.renovacion_auto == 1 else 1
        db.session.commit()
        
        estado_texto = "activada" if alquiler.renovacion_auto == 1 else "desactivada"
        return jsonify({"status": "success", "mensaje": f"Política de renovación {estado_texto}"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": f"Error al cambiar renovación: {str(e)}"}), 500

@shop_bp.route('/plan/<int:id_suscripcion>/toggle_renovacion', methods=['POST'])
@jwt_required()
def toggle_renovacion_plan(id_suscripcion):
    """Alterna la política de renovación automática del nivel de servicio vigente."""
    try:
        usuario_id = get_jwt_identity()
        sub = db.session.query(SuscripcionPlan).filter_by(id_suscripcion=id_suscripcion, id_usuario=usuario_id).first()
        
        if not sub: return jsonify({"status": "error", "mensaje": "Contrato no localizado"}), 404
            
        sub.renovacion_auto = 0 if sub.renovacion_auto == 1 else 1
        db.session.commit()
        return jsonify({"status": "success", "mensaje": "Política de suscripción actualizada"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": f"Fallo en actualización de plan: {str(e)}"}), 500

@shop_bp.route('/alquiler/<int:id_compra>/empezar_ahora', methods=['POST'])
@jwt_required()
def empezar_ahora_alquiler(id_compra):
    """Forzado de activación: Convierte un activo programado en operativo de inmediato."""
    try:
        usuario_id = get_jwt_identity()
        alquiler = db.session.query(Alquila).filter_by(id_compra=id_compra, id_usuario=usuario_id).first()
        
        if not alquiler: return jsonify({"status": "error", "mensaje": "Licencia no localizada"}), 404
        
        ahora_naive = ahora_utc_naive()
        alquiler.periodo_inicio = ahora_naive
        alquiler.periodo_fin = ahora_naive + timedelta(days=30)
        db.session.commit()
        return jsonify({"status": "success", "mensaje": "Licencia activada forzosamente. Ya operativa."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": f"Error en activación forzosa: {str(e)}"}), 500

@shop_bp.route('/plan/<int:id_suscripcion>/empezar_ahora', methods=['POST'])
@jwt_required()
def empezar_ahora_plan(id_suscripcion):
    """Forzado de activación para transiciones de nivel de servicio programadas."""
    try:
        usuario_id = get_jwt_identity()
        sub = db.session.query(SuscripcionPlan).filter_by(id_suscripcion=id_suscripcion, id_usuario=usuario_id).first()
        
        if not sub: return jsonify({"status": "error", "mensaje": "Contrato no localizado"}), 404
        
        ahora_naive = ahora_utc_naive()
        sub.fecha_inicio = ahora_naive
        if sub.fecha_fin: 
            sub.fecha_fin = ahora_naive + timedelta(days=30)
        db.session.commit()
        return jsonify({"status": "success", "mensaje": "Nivel de servicio activado forzosamente."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": f"Fallo en activación de plan: {str(e)}"}), 500

# ==============================================================================
# MÓDULO 4: RESOLUCIÓN DE DEPENDENCIAS (CATÁLOGO DE FLUJOS)
# ==============================================================================

@shop_bp.route('/guia_pipelines', methods=['GET'])
@jwt_required()
def guia_pipelines():
    """
    Construye una matriz de dependencias comparando flujos con activos del usuario
    para determinar viabilidad técnica de ejecución.
    """
    try:
        usuario_id = get_jwt_identity()
        ahora_naive = ahora_utc_naive()
        
        # Bypass global por suscripción Pro
        es_pro_activo = db.session.query(SuscripcionPlan).join(TipoPlan).filter(
            SuscripcionPlan.id_usuario == usuario_id,
            SuscripcionPlan.activo == 1,
            TipoPlan.nombre == 'Pro',
            SuscripcionPlan.fecha_inicio <= ahora_naive,
            (SuscripcionPlan.fecha_fin >= ahora_naive) | (SuscripcionPlan.fecha_fin.is_(None))
        ).first() is not None

        alquileres_activos = db.session.query(Alquila).filter(
            Alquila.id_usuario == usuario_id,
            Alquila.activo == 1,
            Alquila.periodo_inicio <= ahora_naive,
            (Alquila.periodo_fin >= ahora_naive) | (Alquila.periodo_fin.is_(None))
        ).all()
        ids_ias_alquiladas = {a.id_ia for a in alquileres_activos}

        pipelines = db.session.query(Pipeline).filter_by(publico=1, habilitado=1).all()
        resultado = []

        for p in pipelines:
            etapas = db.session.query(PipelineEtapa).filter_by(id_pipeline=p.id_pipeline).order_by(PipelineEtapa.orden).all()
            
            ias_requeridas_dict = {} 
            detalles_etapas = []

            for e in etapas:
                ia_obj = db.session.get(IAModelo, e.id_ia)
                modo_obj = db.session.get(IAModo, e.id_modo)
                
                if ia_obj and ia_obj.id_ia not in ias_requeridas_dict:
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
                "descripcion": p.descripcion or "Flujo de análisis de inferencia secuencial.",
                "ias_requeridas": list(ias_requeridas_dict.values()),
                "etapas": detalles_etapas
            })

        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Error en resolución de dependencias: {str(e)}"}), 500