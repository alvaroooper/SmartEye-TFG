from app.utils.fechas import ahora_utc_naive
from werkzeug.security import generate_password_hash, check_password_hash
from . import db

# ==============================================================================
# ENTIDADES DE RELACIÓN Y TABLAS ASOCIATIVAS
# ==============================================================================

# Implementación de la relación Many-to-Many para el control de acceso (RBAC)
usuario_rol = db.Table('USUARIO_ROL',
    db.Column('id_usuario', db.Integer, db.ForeignKey('USUARIO.id_usuario', ondelete='CASCADE'), primary_key=True),
    db.Column('id_rol', db.Integer, db.ForeignKey('ROL.id_rol', ondelete='RESTRICT'), primary_key=True)
)

# ==============================================================================
# MÓDULO DE IDENTIDAD Y CONTROL DE ACCESO
# ==============================================================================

class Usuario(db.Model):
    """
    Entidad principal de identidad. Gestiona las credenciales, el ciclo de vida 
    de la cuenta y la persistencia de perfiles de seguridad.
    """
    __tablename__ = 'USUARIO'
    id_usuario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nombre_visible = db.Column(db.String(150), nullable=True)
    estado = db.Column(db.String(50), nullable=False, default='activa')
    
    # Metadatos de auditoría con soporte de zona horaria (UTC)
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora_utc_naive)
    actualizado_en = db.Column(db.DateTime, nullable=False, default=ahora_utc_naive, onupdate=ahora_utc_naive)
    borrado_en = db.Column(db.DateTime, nullable=True)

    # Definiciones de relaciones y mapeos bidireccionales
    roles = db.relationship('Rol', secondary=usuario_rol, backref=db.backref('usuarios', lazy='dynamic'))
    pipelines = db.relationship('Pipeline', backref='propietario', lazy=True)
    suscripciones = db.relationship('SuscripcionPlan', backref='usuario_obj', lazy=True)

    def set_password(self, password_plana):
        """Aplica un algoritmo de hashing seguro a la credencial del usuario."""
        self.password_hash = generate_password_hash(password_plana)

    def check_password(self, password_plana):
        """Valida la integridad de la contraseña mediante comparación de hashes."""
        return check_password_hash(self.password_hash, password_plana)

class Rol(db.Model):
    """Definición de perfiles de seguridad y jerarquías de permisos del sistema."""
    __tablename__ = 'ROL'
    id_rol = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    descripcion = db.Column(db.Text, nullable=True)

# ==============================================================================
# MÓDULO DE MONETIZACIÓN Y CATÁLOGO DE SERVICIOS
# ==============================================================================

class TipoPlan(db.Model):
    """Esquema de planes de suscripción y niveles de servicio comerciales."""
    __tablename__ = 'TIPO_PLAN'
    id_plan = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    precio_mensual = db.Column(db.Numeric(10, 2), nullable=True)
    descripcion = db.Column(db.Text, nullable=True)
    habilitado = db.Column(db.Boolean, nullable=False, default=True)

class SuscripcionPlan(db.Model):
    """Persistencia de contratos de suscripción y vigencia de servicios premium."""
    __tablename__ = 'SUSCRIPCION_PLAN'
    id_suscripcion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('USUARIO.id_usuario', ondelete='RESTRICT'), nullable=False)
    id_plan = db.Column(db.Integer, db.ForeignKey('TIPO_PLAN.id_plan', ondelete='RESTRICT'), nullable=False)
    fecha_compra = db.Column(db.DateTime, nullable=False, default=ahora_utc_naive)
    fecha_inicio = db.Column(db.DateTime, nullable=False, default=ahora_utc_naive)
    fecha_fin = db.Column(db.DateTime, nullable=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    renovacion_auto = db.Column(db.Boolean, nullable=False, default=False)
    importe = db.Column(db.Numeric(10, 2), nullable=True)
    referencia_pago = db.Column(db.String(100), nullable=True)

    plan = db.relationship('TipoPlan', backref='suscripciones_asociadas', lazy=True)

# ==============================================================================
# MÓDULO DE MOTORES DE VISIÓN ARTIFICIAL (IA)
# ==============================================================================

class IAModelo(db.Model):
    """Definición técnica de los motores de IA base integrados en la plataforma."""
    __tablename__ = 'IA_MODELO'
    id_ia = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    habilitada = db.Column(db.Boolean, nullable=False, default=True)
    precio = db.Column(db.Numeric(10, 2), nullable=True)
    ruta_servidor = db.Column(db.String(255), nullable=True)
    
    modos = db.relationship('IAModo', backref='modelo_padre', lazy=True)

class IAModo(db.Model):
    """Mapeo de algoritmos especializados y configuraciones de inferencia."""
    __tablename__ = 'IA_MODO'
    id_modo = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_ia = db.Column(db.Integer, db.ForeignKey('IA_MODELO.id_ia', ondelete='RESTRICT'), nullable=False)
    nombre_modo = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    habilitado = db.Column(db.Boolean, nullable=False, default=True)
    config_predeterminada = db.Column(db.Text, nullable=True)
    
    __table_args__ = (
        db.UniqueConstraint('id_modo', 'id_ia', name='uk_ia_modo_id_modo_id_ia'),
        db.UniqueConstraint('id_ia', 'nombre_modo', name='uk_ia_modo_nombre'),
    )

class Alquila(db.Model):
    """Gestión de licencias temporales para motores de IA bajo demanda."""
    __tablename__ = 'ALQUILA'
    id_compra = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('USUARIO.id_usuario', ondelete='RESTRICT'), nullable=False)
    id_ia = db.Column(db.Integer, db.ForeignKey('IA_MODELO.id_ia', ondelete='RESTRICT'), nullable=False)
    fecha_compra = db.Column(db.DateTime, nullable=False, default=ahora_utc_naive)
    periodo_inicio = db.Column(db.DateTime, nullable=True)
    periodo_fin = db.Column(db.DateTime, nullable=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    renovacion_auto = db.Column(db.Boolean, nullable=False, default=False)
    importe = db.Column(db.Numeric(10, 2), nullable=True)
    referencia_pago = db.Column(db.String(100), nullable=True)

# ==============================================================================
# MÓDULO DE ORQUESTACIÓN DE FLUJOS (PIPELINES)
# ==============================================================================

class Pipeline(db.Model):
    """Definición estructural de flujos de trabajo secuenciales (IA Workflows)."""
    __tablename__ = 'PIPELINE'
    id_pipeline = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('USUARIO.id_usuario', ondelete='SET NULL'), nullable=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    habilitado = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora_utc_naive)
    publico = db.Column(db.Integer, default=1)
    
    etapas = db.relationship('PipelineEtapa', backref='pipeline', lazy=True, cascade="all, delete-orphan")

class Ejecucion(db.Model):
    """Auditoría y registro histórico de procesamientos ejecutados en el motor."""
    __tablename__ = 'EJECUCION'
    id_ejecucion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('USUARIO.id_usuario', ondelete='RESTRICT'), nullable=False)
    id_pipeline = db.Column(db.Integer, db.ForeignKey('PIPELINE.id_pipeline', ondelete='RESTRICT'), nullable=False)
    estado = db.Column(db.String(50), nullable=False, default='pendiente')
    duracion_ms = db.Column(db.Integer, nullable=True)
    mensaje_error_user = db.Column(db.Text, nullable=True)
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora_utc_naive)
    config_aplicada = db.Column(db.Text, nullable=True)

class TemporalArchivo(db.Model):
    """Gestión de activos físicos y políticas de retención de archivos temporales."""
    __tablename__ = 'TEMPORAL_ARCHIVO'
    id_temporal = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_ejecucion = db.Column(db.Integer, db.ForeignKey('EJECUCION.id_ejecucion', ondelete='CASCADE'), nullable=False)
    tipo = db.Column(db.String(50), nullable=True)
    ruta_servidor = db.Column(db.String(255), nullable=True)
    token_descarga = db.Column(db.String(255), unique=True, nullable=True)
    expira_en = db.Column(db.DateTime, nullable=True)

class PipelineEtapa(db.Model):
    """Unidad mínima de procesamiento dentro de un flujo secuencial (Pipeline Step)."""
    __tablename__ = 'PIPELINE_ETAPA'
    id_etapa = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_pipeline = db.Column(db.Integer, db.ForeignKey('PIPELINE.id_pipeline', ondelete='CASCADE'), nullable=False)
    id_modo = db.Column(db.Integer, nullable=False)
    id_ia = db.Column(db.Integer, nullable=False)
    orden = db.Column(db.Integer, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    
    __table_args__ = (
        db.ForeignKeyConstraint(['id_modo', 'id_ia'], ['IA_MODO.id_modo', 'IA_MODO.id_ia'], ondelete='RESTRICT'),
        db.UniqueConstraint('id_pipeline', 'nombre', 'orden', name='uk_pipeline_etapa_pipeline_nombre_orden')
    )
    
    modo = db.relationship('IAModo', primaryjoin="and_(PipelineEtapa.id_modo==IAModo.id_modo, PipelineEtapa.id_ia==IAModo.id_ia)")
    modelo = db.relationship('IAModelo', primaryjoin="PipelineEtapa.id_ia == IAModelo.id_ia", foreign_keys=[id_ia], viewonly=True)