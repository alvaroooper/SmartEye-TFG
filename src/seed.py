from app import create_app, db
from app.models import (Usuario, Rol, Pipeline, PipelineEtapa, IAModelo, 
                        IAModo, TipoPlan, SuscripcionPlan, Alquila)
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

app = create_app()

def seed():
    with app.app_context():
        print("--- Reconstruyendo Base de Datos para TFG ---")
        
        # 0. LIMPIEZA Y CREACIÓN
        db.drop_all()
        db.create_all()

        # 1. ROLES
        admin_rol = Rol(id_rol=1, nombre='admin', descripcion='Control total')
        user_rol = Rol(id_rol=2, nombre='usuario', descripcion='Usuario final')
        db.session.add_all([admin_rol, user_rol])

        # 2. MODELOS E IA MODOS
        mp = IAModelo(id_ia=1, nombre='MediaPipe', descripcion='IA de Google', ruta_servidor='models/mp/')
        yolo = IAModelo(id_ia=2, nombre='yolo', descripcion='Detección YOLO', ruta_servidor='models/yolo/')
        db.session.add_all([mp, yolo])

        m_manos = IAModo(id_modo=1, id_ia=1, nombre_modo='manos', descripcion='Detección de manos con MediaPipe', config_predeterminada='configs/mp_manos.json')
        m_pose = IAModo(id_modo=2, id_ia=1, nombre_modo='pose', descripcion='Detección de pose con MediaPipe', config_predeterminada='configs/mp_pose.json')
        m_yolo = IAModo(id_modo=3, id_ia=2, nombre_modo='deteccion', descripcion='Detección con YOLO', config_predeterminada='configs/yolo_deteccion.json')
        m_yolo_recortes = IAModo(id_modo=4, id_ia=2, nombre_modo='recortes_personas', descripcion='Recorta personas y genera imágenes separadas', config_predeterminada='configs/yolo_recortes.json')
        
        db.session.add_all([m_manos, m_pose, m_yolo, m_yolo_recortes])

        # 3. PLANES
        p_basico = TipoPlan(id_plan=1, nombre='Basico', precio_mensual=0.00)
        p_pro = TipoPlan(id_plan=2, nombre='Pro', precio_mensual=19.99)
        db.session.add_all([p_basico, p_pro])

        # 4. USUARIOS
        # Administrador (Sin suscripción)
        admin = Usuario(id_usuario=1, email='admin@tfg.es', username='admin', 
                        password_hash=generate_password_hash('admin123'), nombre_visible='Admin Sistema')
        admin.roles.append(admin_rol)

        # Usuario 1: ALVARO (Plan Básico + Alquiler MediaPipe)
        u_alvaro = Usuario(id_usuario=2, email='alvaro@tfg.es', username='alvaro', 
                           password_hash=generate_password_hash('user123'), nombre_visible='Alvaro (Básico)')
        u_alvaro.roles.append(user_rol)

        # Usuario 2: RAMON (Plan Pro)
        u_ramon = Usuario(id_usuario=3, email='ramon@tfg.es', username='ramon', 
                          password_hash=generate_password_hash('user123'), nombre_visible='Ramón (Pro)')
        u_ramon.roles.append(user_rol)

        db.session.add_all([admin, u_alvaro, u_ramon])
        db.session.flush()

        # 5. ASIGNACIÓN DE PLANES Y ALQUILERES
        # Alvaro: Plan Básico (ID 1) + Alquiler de MediaPipe (IA ID 1)
        db.session.add(SuscripcionPlan(id_usuario=u_alvaro.id_usuario, id_plan=p_basico.id_plan, activo=1))
        db.session.add(Alquila(
            id_usuario=u_alvaro.id_usuario, 
            id_ia=mp.id_ia, 
            activo=1, 
            periodo_inicio=datetime.now(), 
            periodo_fin=datetime.now() + timedelta(days=30),
            importe=5.00
        ))

        # Ramón: Plan Pro (ID 2)
        db.session.add(SuscripcionPlan(id_usuario=u_ramon.id_usuario, id_plan=p_pro.id_plan, activo=1))

        # 6. PIPELINES
        pipe1 = Pipeline(id_pipeline=1, id_usuario=1, nombre='Objetos y pose', publico=1, habilitado=1)
        pipe2 = Pipeline(id_pipeline=2, id_usuario=1, nombre='Detección Manos', publico=1, habilitado=1)
        pipe3 = Pipeline(id_pipeline=3, id_usuario=1, nombre='Pipeline Privado Admin', publico=0, habilitado=1)
        pipe4 = Pipeline(id_pipeline=4, id_usuario=1, nombre='Deteccion pose', publico=1, habilitado=1)
        pipe5 = Pipeline(id_pipeline=5, id_usuario=1, nombre='Pose de múltiples personas (Recorte + Pose)', publico=1, habilitado=1)
        pipe6 = Pipeline(id_pipeline=6, id_usuario=1, nombre='Deteccion pose', publico=1, habilitado=1)

        db.session.add_all([pipe1, pipe2, pipe3, pipe4, pipe5])
        db.session.flush()

        # 7. ETAPAS
        db.session.add(PipelineEtapa(id_pipeline=1, id_modo=3, id_ia=2, orden=1, nombre='Detección'))
        db.session.add(PipelineEtapa(id_pipeline=1, id_modo=2, id_ia=1, orden=2, nombre='Pose'))
        
        db.session.add(PipelineEtapa(id_pipeline=2, id_modo=1, id_ia=1, orden=1, nombre='Manos'))
        
        db.session.add(PipelineEtapa(id_pipeline=4, id_modo=2, id_ia=1, orden=1, nombre='Pose'))

        db.session.add(PipelineEtapa(id_pipeline=5, id_modo=4, id_ia=2, orden=1, nombre='Aislamiento de personas'))
        db.session.add(PipelineEtapa(id_pipeline=5, id_modo=2, id_ia=1, orden=2, nombre='Pose Individual'))

        db.session.add(PipelineEtapa(id_pipeline=6, id_modo=4, id_ia=2, orden=1, nombre='Aislamiento de personas'))

        db.session.commit()
        print("¡Base de datos recreada con éxito!")

if __name__ == '__main__':
    seed()