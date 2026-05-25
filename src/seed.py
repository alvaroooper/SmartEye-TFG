from datetime import timedelta
from app.utils.fechas import ahora_utc_naive
from werkzeug.security import generate_password_hash
from sqlalchemy import text

from app import create_app, db
from app.models import (
    Usuario, Rol, Pipeline, PipelineEtapa, IAModelo,
    IAModo, TipoPlan, SuscripcionPlan, Alquila
)

app = create_app()


def aplicar_restricciones_bd():
    """
    Añade restricciones adicionales al esquema creado por SQLAlchemy.

    Estas restricciones refuerzan reglas de negocio importantes:
    - Importes no negativos.
    - Coherencia entre fechas de inicio y fin.
    - Duraciones no negativas.
    - Orden positivo en las etapas de un pipeline.
    - Nombres de pipelines no repetidos para un mismo usuario.
    """

    dialecto = db.engine.dialect.name

    # Estas sentencias están pensadas para MariaDB/MySQL.
    # En SQLite, por ejemplo durante pruebas, se omiten para evitar incompatibilidades.
    if dialecto not in ("mysql", "mariadb"):
        print(f"--- Aviso: restricciones SQL adicionales no aplicadas para dialecto {dialecto} ---")
        return

    restricciones = [
        # TIPO_PLAN: evita precios mensuales negativos.
        """
        ALTER TABLE TIPO_PLAN
        ADD CONSTRAINT chk_tipo_plan_precio_mensual
        CHECK (precio_mensual IS NULL OR precio_mensual >= 0)
        """,

        # SUSCRIPCION_PLAN: evita importes negativos y fechas incoherentes.
        """
        ALTER TABLE SUSCRIPCION_PLAN
        ADD CONSTRAINT chk_suscripcion_plan_importe
        CHECK (importe IS NULL OR importe >= 0)
        """,
        """
        ALTER TABLE SUSCRIPCION_PLAN
        ADD CONSTRAINT chk_suscripcion_plan_fechas
        CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio)
        """,

        # IA_MODELO: evita precios negativos en el catálogo de modelos.
        """
        ALTER TABLE IA_MODELO
        ADD CONSTRAINT chk_ia_modelo_precio
        CHECK (precio IS NULL OR precio >= 0)
        """,

        # ALQUILA: evita importes negativos y periodos incoherentes.
        """
        ALTER TABLE ALQUILA
        ADD CONSTRAINT chk_alquila_importe
        CHECK (importe IS NULL OR importe >= 0)
        """,
        """
        ALTER TABLE ALQUILA
        ADD CONSTRAINT chk_alquila_periodo
        CHECK (periodo_fin IS NULL OR periodo_inicio IS NULL OR periodo_fin >= periodo_inicio)
        """,

        # PIPELINE: evita que un mismo usuario tenga dos pipelines con el mismo nombre.
        """
        ALTER TABLE PIPELINE
        ADD CONSTRAINT uk_pipeline_usuario_nombre
        UNIQUE (id_usuario, nombre)
        """,

        # EJECUCION: evita duraciones negativas.
        """
        ALTER TABLE EJECUCION
        ADD CONSTRAINT chk_ejecucion_duracion
        CHECK (duracion_ms IS NULL OR duracion_ms >= 0)
        """,

        # PIPELINE_ETAPA: obliga a que el orden de las etapas sea positivo.
        """
        ALTER TABLE PIPELINE_ETAPA
        ADD CONSTRAINT chk_pipeline_etapa_orden
        CHECK (orden >= 1)
        """
    ]

    for restriccion in restricciones:
        db.session.execute(text(restriccion))

    db.session.commit()
    print("--- Restricciones adicionales aplicadas correctamente ---")


def seed():
    """
    Script de población inicial de la base de datos.

    Establece la configuración base del sistema:
    - Roles.
    - Usuarios de prueba.
    - Modelos de inteligencia artificial.
    - Modos de ejecución.
    - Planes y contrataciones iniciales.
    - Pipelines preconfigurados.
    - Etapas de cada pipeline.
    """

    with app.app_context():
        print("--- Inicializando persistencia de datos (Entorno TFG) ---")

        # 1. REESTABLECIMIENTO DEL ESQUEMA
        # Se asegura un estado limpio de la base de datos eliminando tablas existentes.
        db.drop_all()
        db.create_all()
        aplicar_restricciones_bd()

        ahora = ahora_utc_naive()

        # 2. DEFINICIÓN DE PERFILES DE ACCESO
        admin_rol = Rol(
            id_rol=1,
            nombre="admin",
            descripcion="Control total del sistema, auditoría y gestión de usuarios"
        )

        user_rol = Rol(
            id_rol=2,
            nombre="usuario",
            descripcion="Usuario final con acceso a herramientas de análisis y catálogo"
        )

        db.session.add_all([admin_rol, user_rol])

        # 3. CATÁLOGO DE MOTORES DE INTELIGENCIA ARTIFICIAL
        mp = IAModelo(
            id_ia=1,
            nombre="MediaPipe",
            descripcion="Framework de Google para soluciones de ML en visión artificial",
            ruta_servidor="models/mp/",
            precio=9.99
        )

        yolo = IAModelo(
            id_ia=2,
            nombre="yolo",
            descripcion="Algoritmo de detección de objetos You Only Look Once (YOLOv8)",
            ruta_servidor="models/yolo/",
            precio=9.99
        )

        db.session.add_all([mp, yolo])

        # 4. MODOS DE EJECUCIÓN DE CADA MODELO
        m_manos = IAModo(
            id_modo=1,
            id_ia=1,
            nombre_modo="manos",
            descripcion="Detección y seguimiento de puntos clave palmares",
            config_predeterminada="configs/mp_manos.json"
        )

        m_pose = IAModo(
            id_modo=2,
            id_ia=1,
            nombre_modo="pose",
            descripcion="Estimación de pose humana y puntos esqueléticos",
            config_predeterminada="configs/mp_pose.json"
        )

        m_yolo = IAModo(
            id_modo=3,
            id_ia=2,
            nombre_modo="deteccion",
            descripcion="Detección multiclase de objetos genéricos en tiempo real",
            config_predeterminada="configs/yolo_deteccion.json"
        )

        m_yolo_recortes = IAModo(
            id_modo=4,
            id_ia=2,
            nombre_modo="recortes_personas",
            descripcion="Localización y extracción de sujetos en archivos independientes",
            config_predeterminada="configs/yolo_recortes.json"
        )

        db.session.add_all([m_manos, m_pose, m_yolo, m_yolo_recortes])

        # 5. CATÁLOGO COMERCIAL
        p_basico = TipoPlan(
            id_plan=1,
            nombre="Basico",
            precio_mensual=0.00,
            descripcion="Plan de entrada con funcionalidades limitadas de análisis"
        )

        p_pro = TipoPlan(
            id_plan=2,
            nombre="Pro",
            precio_mensual=19.99,
            descripcion="Plan profesional con acceso total al catálogo de modelos y flujos"
        )

        db.session.add_all([p_basico, p_pro])

        # 6. USUARIOS DE PRUEBA
        admin = Usuario(
            id_usuario=1,
            email="admin@tfg.es",
            username="admin",
            password_hash=generate_password_hash("Admin123"),
            nombre_visible="Administrador Principal"
        )
        admin.roles.append(admin_rol)

        u_pepe = Usuario(
            id_usuario=2,
            email="pepe@tfg.es",
            username="pepe",
            password_hash=generate_password_hash("User123"),
            nombre_visible="Pepe Pérez"
        )
        u_pepe.roles.append(user_rol)

        u_ramon = Usuario(
            id_usuario=3,
            email="ramon@tfg.es",
            username="ramon",
            password_hash=generate_password_hash("User123"),
            nombre_visible="Ramón García"
        )
        u_ramon.roles.append(user_rol)

        db.session.add_all([admin, u_pepe, u_ramon])
        db.session.flush()

        # 7. CONTRATOS Y SERVICIOS ACTIVOS
        db.session.add(
            SuscripcionPlan(
                id_usuario=u_pepe.id_usuario,
                id_plan=p_basico.id_plan,
                activo=1,
                importe=p_basico.precio_mensual
            )
        )

        db.session.add(
            Alquila(
                id_usuario=u_pepe.id_usuario,
                id_ia=mp.id_ia,
                activo=1,
                periodo_inicio=ahora,
                periodo_fin=ahora + timedelta(days=30),
                importe=mp.precio
            )
        )

        db.session.add(
            SuscripcionPlan(
                id_usuario=u_ramon.id_usuario,
                id_plan=p_pro.id_plan,
                activo=1,
                fecha_fin=ahora + timedelta(days=30),
                importe=p_pro.precio_mensual
            )
        )

        # 8. CATÁLOGO DE PIPELINES
        pipe1 = Pipeline(
            id_pipeline=1,
            id_usuario=1,
            nombre="Identificación de Manos",
            publico=1,
            habilitado=1,
            descripcion="Análisis especializado en puntos clave palmares y gestualidad."
        )

        pipe2 = Pipeline(
            id_pipeline=2,
            id_usuario=1,
            nombre="Identificación de pose",
            publico=1,
            habilitado=1,
            descripcion="Reconstrucción de la estructura corporal mediante landmarks."
        )

        pipe3 = Pipeline(
            id_pipeline=3,
            id_usuario=1,
            nombre="Detección Objetos",
            publico=1,
            habilitado=1,
            descripcion="Identificación de objetos en una imagen mediante detección multiclase."
        )

        pipe4 = Pipeline(
            id_pipeline=4,
            id_usuario=1,
            nombre="Aislamiento de personas",
            publico=1,
            habilitado=1,
            descripcion="Extracción de sujetos mediante recortes independientes."
        )

        pipe5 = Pipeline(
            id_pipeline=5,
            id_usuario=1,
            nombre="Detección de objetos y pose individual",
            publico=1,
            habilitado=1,
            descripcion="Análisis dual basado en detección de objetos y estimación de pose."
        )

        pipe6 = Pipeline(
            id_pipeline=6,
            id_usuario=1,
            nombre="Análisis Multi-Sujeto (Recorte + Pose)",
            publico=1,
            habilitado=1,
            descripcion="Aislamiento de individuos en imágenes separadas para analizar la pose de cada sujeto."
        )

        pipe7 = Pipeline(
            id_pipeline=7,
            id_usuario=1,
            nombre="Análisis Multi-Sujeto (Recorte + Manos)",
            publico=1,
            habilitado=1,
            descripcion="Aislamiento de individuos en imágenes separadas para analizar las manos de cada sujeto."
        )

        pipe8 = Pipeline(
            id_pipeline=8,
            id_usuario=1,
            nombre="Pipeline Privado Admin",
            publico=0,
            habilitado=0,
            descripcion="Entorno de pruebas restringido para auditoría administrativa."
        )

        db.session.add_all([pipe1, pipe2, pipe3, pipe4, pipe5, pipe6, pipe7, pipe8])
        db.session.flush()

        # 9. ETAPAS DE LOS PIPELINES

        # Pipeline 1: Manos
        db.session.add(
            PipelineEtapa(
                id_pipeline=1,
                id_modo=1,
                id_ia=1,
                orden=1,
                nombre="Seguimiento de Manos",
                descripcion="Identificación de landmarks palmares bilaterales."
            )
        )

        # Pipeline 2: Pose directa
        db.session.add(
            PipelineEtapa(
                id_pipeline=2,
                id_modo=2,
                id_ia=1,
                orden=1,
                nombre="Estimación de Pose",
                descripcion="Reconstrucción esquelética virtual."
            )
        )

        # Pipeline 3: Detección de objetos
        db.session.add(
            PipelineEtapa(
                id_pipeline=3,
                id_modo=3,
                id_ia=2,
                orden=1,
                nombre="Reconocimiento de objetos",
                descripcion="Identificación de distintos objetos de una imagen junto con sus niveles de confianza."
            )
        )

        # Pipeline 4: Recorte de personas
        db.session.add(
            PipelineEtapa(
                id_pipeline=4,
                id_modo=4,
                id_ia=2,
                orden=1,
                nombre="Aislamiento de Sujetos",
                descripcion="Generación de archivos independientes por cada individuo localizado."
            )
        )

        # Pipeline 5: Detección -> Pose
        db.session.add(
            PipelineEtapa(
                id_pipeline=5,
                id_modo=3,
                id_ia=2,
                orden=1,
                nombre="Detección de Objetos",
                descripcion="Localización de objetos multiclase basada en YOLOv8."
            )
        )

        db.session.add(
            PipelineEtapa(
                id_pipeline=5,
                id_modo=2,
                id_ia=1,
                orden=2,
                nombre="Análisis de Pose",
                descripcion="Mapeo esquelético sobre el sujeto identificado."
            )
        )

        # Pipeline 6: Recorte -> Pose individual
        db.session.add(
            PipelineEtapa(
                id_pipeline=6,
                id_modo=4,
                id_ia=2,
                orden=1,
                nombre="Aislamiento y Escalado",
                descripcion="Segmentación de individuos y escalado de imágenes."
            )
        )

        db.session.add(
            PipelineEtapa(
                id_pipeline=6,
                id_modo=2,
                id_ia=1,
                orden=2,
                nombre="Análisis de Pose Detallada",
                descripcion="Estimación esquelética aplicada a recortes de personas."
            )
        )

        # Pipeline 7: Recorte -> Manos individual
        db.session.add(
            PipelineEtapa(
                id_pipeline=7,
                id_modo=4,
                id_ia=2,
                orden=1,
                nombre="Aislamiento y Escalado",
                descripcion="Segmentación de individuos y escalado de imágenes."
            )
        )

        db.session.add(
            PipelineEtapa(
                id_pipeline=7,
                id_modo=1,
                id_ia=1,
                orden=2,
                nombre="Análisis de Manos Detallado",
                descripcion="Identificación de manos en cada imagen de sujeto aislado."
            )
        )

        # Pipeline 8: Privado
        db.session.add(
            PipelineEtapa(
                id_pipeline=8,
                id_modo=1,
                id_ia=1,
                orden=1,
                nombre="Seguimiento de Manos",
                descripcion="Identificación de landmarks palmares bilaterales."
            )
        )

        db.session.commit()
        print("--- Proceso de inicialización de base de datos completado con éxito ---")


if __name__ == "__main__":
    seed()