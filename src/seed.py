from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from app import create_app, db
from app.models import (Usuario, Rol, Pipeline, PipelineEtapa, IAModelo, 
                        IAModo, TipoPlan, SuscripcionPlan, Alquila)

app = create_app()

def seed():
    """
    Script de población inicial (seeding) de la base de datos.
    Establece la configuración base del sistema, incluyendo roles, modelos de IA,
    catálogo comercial y pipelines preconfigurados.
    """
    with app.app_context():
        print("--- Inicializando persistencia de datos (Entorno TFG) ---")
        
        # 1. REESTABLECIMIENTO DEL ESQUEMA
        # Se asegura un estado limpio de la base de datos eliminando tablas existentes
        db.drop_all()
        db.create_all()

        # 2. DEFINICIÓN DE PERFILES DE ACCESO (RBAC)
        # Configuración de los niveles de privilegio del sistema
        admin_rol = Rol(id_rol=1, nombre='admin', 
                        descripcion='Control total del sistema, auditoría y gestión de usuarios')
        user_rol = Rol(id_rol=2, nombre='usuario', 
                       descripcion='Usuario final con acceso a herramientas de análisis y catálogo')
        db.session.add_all([admin_rol, user_rol])

        # 3. CATÁLOGO DE MOTORES DE INTELIGENCIA ARTIFICIAL
        # Registro de proveedores de modelos y sus metadatos técnicos
        mp = IAModelo(id_ia=1, nombre='MediaPipe', 
                      descripcion='Framework de Google para soluciones de ML en visión artificial', 
                      ruta_servidor='models/mp/', precio=9.99)
        yolo = IAModelo(id_ia=2, nombre='yolo', 
                        descripcion='Algoritmo de detección de objetos You Only Look Once (YOLOv8)', 
                        ruta_servidor='models/yolo/', precio=9.99)
        db.session.add_all([mp, yolo])

        # Configuración de modos de ejecución específicos para cada motor de IA
        m_manos = IAModo(id_modo=1, id_ia=1, nombre_modo='manos', 
                         descripcion='Detección y seguimiento de puntos clave palmares', 
                         config_predeterminada='configs/mp_manos.json')
        m_pose = IAModo(id_modo=2, id_ia=1, nombre_modo='pose', 
                        descripcion='Estimación de pose humana y puntos esqueléticos', 
                        config_predeterminada='configs/mp_pose.json')
        m_yolo = IAModo(id_modo=3, id_ia=2, nombre_modo='deteccion', 
                        descripcion='Detección multiclase de objetos genéricos en tiempo real', 
                        config_predeterminada='configs/yolo_deteccion.json')
        m_yolo_recortes = IAModo(id_modo=4, id_ia=2, nombre_modo='recortes_personas', 
                                 descripcion='Localización y extracción de sujetos en archivos independientes', 
                                 config_predeterminada='configs/yolo_recortes.json')
        
        db.session.add_all([m_manos, m_pose, m_yolo, m_yolo_recortes])

        # 4. DEFINICIÓN DEL CATÁLOGO COMERCIAL
        # Estructura de costes y beneficios por nivel de suscripción
        p_basico = TipoPlan(id_plan=1, nombre='Basico', precio_mensual=0.00, 
                            descripcion='Plan de entrada con funcionalidades limitadas de análisis')
        p_pro = TipoPlan(id_plan=2, nombre='Pro', precio_mensual=19.99, 
                         descripcion='Plan profesional con acceso total al catálogo de modelos y flujos')
        db.session.add_all([p_basico, p_pro])

        # 5. POBLACIÓN DE IDENTIDADES DE USUARIO
        # Registro de usuarios de prueba con contraseñas cifradas
        admin = Usuario(id_usuario=1, email='admin@tfg.es', username='admin', 
                        password_hash=generate_password_hash('Admin123'), 
                        nombre_visible='Administrador Principal')
        admin.roles.append(admin_rol)

        u_alvaro = Usuario(id_usuario=2, email='pepe@tfg.es', username='pepe', 
                           password_hash=generate_password_hash('User123'), 
                           nombre_visible='Pepe Pérez')
        u_alvaro.roles.append(user_rol)

        u_ramon = Usuario(id_usuario=3, email='ramon@tfg.es', username='ramon', 
                          password_hash=generate_password_hash('User123'), 
                          nombre_visible='Ramón García')
        u_ramon.roles.append(user_rol)

        db.session.add_all([admin, u_alvaro, u_ramon])
        db.session.flush()

        # 6. GESTIÓN DE CONTRATOS Y SERVICIOS ACTIVOS
        # Asignación de planes y alquileres individuales de modelos de IA
        db.session.add(SuscripcionPlan(id_usuario=u_alvaro.id_usuario, id_plan=p_basico.id_plan, 
                                      activo=1, importe=p_basico.precio_mensual))
        db.session.add(Alquila(id_usuario=u_alvaro.id_usuario, id_ia=mp.id_ia, activo=1, 
                               periodo_inicio=datetime.now(), 
                               periodo_fin=datetime.now() + timedelta(days=30), importe=mp.precio))
        db.session.add(SuscripcionPlan(id_usuario=u_ramon.id_usuario, id_plan=p_pro.id_plan, 
                                      activo=1, fecha_fin=datetime.now() + timedelta(days=30), 
                                      importe=p_pro.precio_mensual))

        # 7. CATÁLOGO DE FLUJOS DE ANÁLISIS (PIPELINES)
        # Configuración de pipelines públicos y privados para pruebas de acceso
        pipe1 = Pipeline(id_pipeline=1, id_usuario=1, nombre='Objetos y pose', publico=1, habilitado=1, 
                         descripcion='Análisis dual: detección multiclase y estimación de pose simultánea.')
        pipe2 = Pipeline(id_pipeline=2, id_usuario=1, nombre='Detección Manos', publico=1, habilitado=1, 
                         descripcion='Flujo especializado en puntos clave palmares y gestualidad.')
        pipe3 = Pipeline(id_pipeline=3, id_usuario=1, nombre='Pipeline Privado Admin', publico=0, habilitado=1, 
                         descripcion='Entorno de pruebas restringido para auditoría administrativa.')
        pipe4 = Pipeline(id_pipeline=4, id_usuario=1, nombre='Deteccion pose', publico=1, habilitado=1, 
                         descripcion='Reconstrucción integral de la estructura ósea humana.')
        pipe5 = Pipeline(id_pipeline=5, id_usuario=1, nombre='Análisis Multi-Sujeto (Recorte + Pose)', publico=1, habilitado=1, 
                         descripcion='Pipeline avanzado con aislamiento de individuos para análisis de pose de alta precisión.')
        pipe6 = Pipeline(id_pipeline=6, id_usuario=1, nombre='Aislamiento de personas', publico=1, habilitado=1, 
                         descripcion='Extracción de sujetos mediante segmentación YOLO para descargas independientes.')

        db.session.add_all([pipe1, pipe2, pipe3, pipe4, pipe5, pipe6])
        db.session.flush()

        # 8. ARQUITECTURA SECUENCIAL DE ETAPAS
        # Definición de la lógica de encadenamiento entre modelos de IA dentro de los pipelines
        
        # Pipeline 1: Detección -> Pose
        db.session.add(PipelineEtapa(id_pipeline=1, id_modo=3, id_ia=2, orden=1, nombre='Detección de Objetos', 
                                     descripcion='Localización multiclase basada en YOLOv8.'))
        db.session.add(PipelineEtapa(id_pipeline=1, id_modo=2, id_ia=1, orden=2, nombre='Análisis de Pose', 
                                     descripcion='Mapeo esquelético sobre sujetos identificados.'))
        
        # Pipeline 2: Manos
        db.session.add(PipelineEtapa(id_pipeline=2, id_modo=1, id_ia=1, orden=1, nombre='Seguimiento de Manos', 
                                     descripcion='Identificación de landmarks palmares bilaterales.'))
        
        # Pipeline 4: Pose Directa
        db.session.add(PipelineEtapa(id_pipeline=4, id_modo=2, id_ia=1, orden=1, nombre='Estimación de Pose', 
                                     descripcion='Reconstrucción esquelética virtual.'))

        # Pipeline 5: Detección con Recorte -> Pose Individual
        db.session.add(PipelineEtapa(id_pipeline=5, id_modo=4, id_ia=2, orden=1, nombre='Aislamiento y Escalado', 
                                     descripcion='Segmentación de individuos y optimización de ROI (Region of Interest).'))
        db.session.add(PipelineEtapa(id_pipeline=5, id_modo=2, id_ia=1, orden=2, nombre='Análisis de Pose Detallada', 
                                     descripcion='Estimación esquelética aplicada a recortes normalizados.'))

        # Pipeline 6: Recorte de Personas
        db.session.add(PipelineEtapa(id_pipeline=6, id_modo=4, id_ia=2, orden=1, nombre='Aislamiento de Sujetos', 
                                     descripcion='Generación de archivos independientes por cada individuo localizado.'))

        db.session.commit()
        print("--- Proceso de inicialización completado con éxito ---")

if __name__ == '__main__':
    seed()