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
        admin_rol = Rol(id_rol=1, nombre='admin', descripcion='Control total del sistema y gestión de usuarios')
        user_rol = Rol(id_rol=2, nombre='usuario', descripcion='Usuario final con acceso a herramientas de análisis')
        db.session.add_all([admin_rol, user_rol])

        # 2. MODELOS E IA MODOS (Configurados con precio base de 9.99 €)
        mp = IAModelo(id_ia=1, nombre='MediaPipe', descripcion='Framework de Google para soluciones de ML en visión artificial', ruta_servidor='models/mp/', precio=9.99)
        yolo = IAModelo(id_ia=2, nombre='yolo', descripcion='You Only Look Once: Detección de objetos de última generación', ruta_servidor='models/yolo/', precio=9.99)
        db.session.add_all([mp, yolo])

        m_manos = IAModo(id_modo=1, id_ia=1, nombre_modo='manos', descripcion='Detección y seguimiento de puntos clave de las manos', config_predeterminada='configs/mp_manos.json')
        m_pose = IAModo(id_modo=2, id_ia=1, nombre_modo='pose', descripcion='Estimación de pose humana', config_predeterminada='configs/mp_pose.json')
        m_yolo = IAModo(id_modo=3, id_ia=2, nombre_modo='deteccion', descripcion='Detección multiclase de objetos genéricos', config_predeterminada='configs/yolo_deteccion.json')
        m_yolo_recortes = IAModo(id_modo=4, id_ia=2, nombre_modo='recortes_personas', descripcion='Localización y extracción de individuos en archivos separados', config_predeterminada='configs/yolo_recortes.json')
        
        db.session.add_all([m_manos, m_pose, m_yolo, m_yolo_recortes])

        # 3. PLANES
        p_basico = TipoPlan(id_plan=1, nombre='Basico', precio_mensual=0.00, descripcion='Funcionalidades esenciales para usuarios individuales')
        p_pro = TipoPlan(id_plan=2, nombre='Pro', precio_mensual=19.99, descripcion='Acceso ilimitado a todos los modelos y pipelines')
        db.session.add_all([p_basico, p_pro])

        # 4. USUARIOS
        # Administrador
        admin = Usuario(id_usuario=1, email='admin@tfg.es', username='admin', 
                        password_hash=generate_password_hash('Admin123'), nombre_visible='Administrador Principal')
        admin.roles.append(admin_rol)

        # Usuario 1: PEPE (Plan Básico + Alquiler MediaPipe)
        u_alvaro = Usuario(id_usuario=2, email='pepe@tfg.es', username='pepe', 
                           password_hash=generate_password_hash('User123'), nombre_visible='Pepe Pérez')
        u_alvaro.roles.append(user_rol)

        # Usuario 2: RAMÓN (Plan Pro)
        u_ramon = Usuario(id_usuario=3, email='ramon@tfg.es', username='ramon', 
                          password_hash=generate_password_hash('User123'), nombre_visible='Ramón García')
        u_ramon.roles.append(user_rol)

        db.session.add_all([admin, u_alvaro, u_ramon])
        db.session.flush()

        # 5. ASIGNACIÓN DE PLANES Y ALQUILERES
        db.session.add(SuscripcionPlan(id_usuario=u_alvaro.id_usuario, id_plan=p_basico.id_plan, activo=1, importe=p_basico.precio_mensual))
        db.session.add(Alquila(id_usuario=u_alvaro.id_usuario, id_ia=mp.id_ia, activo=1, periodo_inicio=datetime.now(), periodo_fin=datetime.now() + timedelta(days=30), importe=mp.precio))
        db.session.add(SuscripcionPlan(id_usuario=u_ramon.id_usuario, id_plan=p_pro.id_plan, activo=1, fecha_fin=datetime.now() + timedelta(days=30), importe=p_pro.precio_mensual))

        # 6. PIPELINES
        pipe1 = Pipeline(id_pipeline=1, id_usuario=1, nombre='Objetos y pose', publico=1, habilitado=1, descripcion='Análisis dual que detecta objetos en la escena y calcula la pose de personas.')
        pipe2 = Pipeline(id_pipeline=2, id_usuario=1, nombre='Detección Manos', publico=1, habilitado=1, descripcion='Especializado en el reconocimiento de puntos clave y gestos de las manos.')
        pipe3 = Pipeline(id_pipeline=3, id_usuario=1, nombre='Pipeline Privado Admin', publico=0, habilitado=1, descripcion='Pipeline de pruebas técnicas reservado para administración.')
        pipe4 = Pipeline(id_pipeline=4, id_usuario=1, nombre='Deteccion pose', publico=1, habilitado=1, descripcion='Realiza una estimación completa del esqueleto humano en la imagen.')
        pipe5 = Pipeline(id_pipeline=5, id_usuario=1, nombre='Pose de múltiples personas (Recorte + Pose)', publico=1, habilitado=1, descripcion='Pipeline avanzado que aísla a cada persona antes de calcular su pose individual para mayor precisión.')
        pipe6 = Pipeline(id_pipeline=6, id_usuario=1, nombre='Aislamiento de personas', publico=1, habilitado=1, descripcion='Utiliza YOLO para identificar y extraer imágenes individuales de cada persona en la escena.')

        db.session.add_all([pipe1, pipe2, pipe3, pipe4, pipe5, pipe6])
        db.session.flush()

        # 7. ETAPAS CON DESCRIPCIONES DETALLADAS
        # Pipeline 1
        db.session.add(PipelineEtapa(id_pipeline=1, id_modo=3, id_ia=2, orden=1, nombre='Detección de Objetos', 
                                     descripcion='Identifica y localiza más de 80 clases de objetos comunes mediante el modelo YOLOv8.'))
        db.session.add(PipelineEtapa(id_pipeline=1, id_modo=2, id_ia=1, orden=2, nombre='Análisis de Pose', 
                                     descripcion='Mapea los puntos clave del cuerpo humano sobre los sujetos detectados para analizar su posición.'))
        
        # Pipeline 2
        db.session.add(PipelineEtapa(id_pipeline=2, id_modo=1, id_ia=1, orden=1, nombre='Seguimiento de Manos', 
                                     descripcion='Localiza puntos de referencia por mano, diferenciando entre mano izquierda y derecha.'))
        
        # Pipeline 4
        db.session.add(PipelineEtapa(id_pipeline=4, id_modo=2, id_ia=1, orden=1, nombre='Estimación de Pose', 
                                     descripcion='Reconstruye el esqueleto virtual del usuario.'))

        # Pipeline 5
        db.session.add(PipelineEtapa(id_pipeline=5, id_modo=4, id_ia=2, orden=1, nombre='Recorte y Escalado', 
                                     descripcion='Detecta individuos y genera recortes escalados con redimensión cúbica para optimizar el análisis de pose posterior.'))
        db.session.add(PipelineEtapa(id_pipeline=5, id_modo=2, id_ia=1, orden=2, nombre='Pose Individual', 
                                     descripcion='Calcula la pose detallada para cada uno de los recortes de personas generados en la etapa previa.'))

        # Pipeline 6
        db.session.add(PipelineEtapa(id_pipeline=6, id_modo=4, id_ia=2, orden=1, nombre='Aislamiento de Sujetos', 
                                     descripcion='Extrae a cada persona detectada de la imagen original y los guarda como archivos independientes para su descarga.'))

        db.session.commit()
        print("¡Base de datos recreada con éxito!")

if __name__ == '__main__':
    seed()