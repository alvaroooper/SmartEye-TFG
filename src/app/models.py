from . import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Tabla intermedia para la relación N:M entre USUARIO y ROL
usuario_rol = db.Table('USUARIO_ROL',
    db.Column('id_usuario', db.Integer, db.ForeignKey('USUARIO.id_usuario', ondelete='CASCADE'), primary_key=True),
    db.Column('id_rol', db.Integer, db.ForeignKey('ROL.id_rol', ondelete='RESTRICT'), primary_key=True)
)

class Usuario(db.Model):
    __tablename__ = 'USUARIO'
    id_usuario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nombre_visible = db.Column(db.String(150), nullable=True)
    estado_cuenta = db.Column(db.String(50), nullable=False, default='activa')
    creado_en = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    borrado_en = db.Column(db.DateTime, nullable=True)

    # Relaciones
    roles = db.relationship('Rol', secondary=usuario_rol, backref=db.backref('usuarios', lazy='dynamic'))
    pipelines = db.relationship('Pipeline', backref='propietario', lazy=True)
    suscripciones = db.relationship('SuscripcionPlan', backref='usuario_obj', lazy=True)

    # --- MÉTODOS DE SEGURIDAD ---
    def set_password(self, password_plana):
        """Convierte la contraseña en texto plano a un hash indescifrable y lo guarda"""
        self.password_hash = generate_password_hash(password_plana)

    def check_password(self, password_plana):
        """Compara la contraseña plana introducida en el login con el hash de la BD"""
        return check_password_hash(self.password_hash, password_plana)

class Rol(db.Model):
    __tablename__ = 'ROL'
    id_rol = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    descripcion = db.Column(db.Text, nullable=True)

class TipoPlan(db.Model):
    __tablename__ = 'TIPO_PLAN'
    id_plan = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    precio_mensual = db.Column(db.Numeric(10, 2), nullable=True)
    habilitado = db.Column(db.Boolean, nullable=False, default=True)

class SuscripcionPlan(db.Model):
    __tablename__ = 'SUSCRIPCION_PLAN'
    id_suscripcion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('USUARIO.id_usuario', ondelete='RESTRICT'), nullable=False)
    id_plan = db.Column(db.Integer, db.ForeignKey('TIPO_PLAN.id_plan', ondelete='RESTRICT'), nullable=False)
    fecha_compra = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    fecha_inicio = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    fecha_fin = db.Column(db.DateTime, nullable=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    renovacion_auto = db.Column(db.Boolean, nullable=False, default=False)
    importe = db.Column(db.Numeric(10, 2), nullable=True)
    referencia_pago = db.Column(db.String(100), nullable=True)

    # Relaciones
    plan = db.relationship('TipoPlan', backref='suscripciones_asociadas', lazy=True)

class IAModelo(db.Model):
    __tablename__ = 'IA_MODELO'
    id_ia = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    habilitada = db.Column(db.Boolean, nullable=False, default=True)
    precio = db.Column(db.Numeric(10, 2), nullable=True)
    ruta_servidor = db.Column(db.String(255), nullable=True)
    
    modos = db.relationship('IAModo', backref='modelo_padre', lazy=True)

class IAModo(db.Model):
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
    __tablename__ = 'ALQUILA'
    id_compra = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('USUARIO.id_usuario', ondelete='RESTRICT'), nullable=False)
    id_ia = db.Column(db.Integer, db.ForeignKey('IA_MODELO.id_ia', ondelete='RESTRICT'), nullable=False)
    fecha_compra = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    periodo_inicio = db.Column(db.DateTime, nullable=True)
    periodo_fin = db.Column(db.DateTime, nullable=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    renovacion_auto = db.Column(db.Boolean, nullable=False, default=False)
    importe = db.Column(db.Numeric(10, 2), nullable=True)
    referencia_pago = db.Column(db.String(100), nullable=True)

class Pipeline(db.Model):
    __tablename__ = 'PIPELINE'
    id_pipeline = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('USUARIO.id_usuario', ondelete='SET NULL'), nullable=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    habilitado = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    etapas = db.relationship('PipelineEtapa', backref='pipeline', lazy=True, cascade="all, delete-orphan")

class Ejecucion(db.Model):
    __tablename__ = 'EJECUCION'
    id_ejecucion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('USUARIO.id_usuario', ondelete='RESTRICT'), nullable=False)
    id_pipeline = db.Column(db.Integer, db.ForeignKey('PIPELINE.id_pipeline', ondelete='RESTRICT'), nullable=False)
    origen = db.Column(db.String(100), nullable=True)
    estado = db.Column(db.String(50), nullable=False, default='pendiente')
    duracion_ms = db.Column(db.Integer, nullable=True)
    mensaje_error_user = db.Column(db.Text, nullable=True)
    creado_en = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    config_aplicada = db.Column(db.Text, nullable=True)

class TemporalArchivo(db.Model):
    __tablename__ = 'TEMPORAL_ARCHIVO'
    id_temporal = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_ejecucion = db.Column(db.Integer, db.ForeignKey('EJECUCION.id_ejecucion', ondelete='CASCADE'), nullable=False)
    tipo = db.Column(db.String(50), nullable=True)
    ruta_servidor = db.Column(db.String(255), nullable=True)
    token_descarga = db.Column(db.String(255), unique=True, nullable=True)
    expira_en = db.Column(db.DateTime, nullable=True)

class PipelineEtapa(db.Model):
    __tablename__ = 'PIPELINE_ETAPA'
    id_etapa = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_pipeline = db.Column(db.Integer, db.ForeignKey('PIPELINE.id_pipeline', ondelete='CASCADE'), nullable=False)
    id_modo = db.Column(db.Integer, nullable=False)
    id_ia = db.Column(db.Integer, nullable=False)
    orden = db.Column(db.Integer, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    
    # Clave foránea compuesta que mapea directamente a IA_MODO
    __table_args__ = (
        db.ForeignKeyConstraint(['id_modo', 'id_ia'], ['IA_MODO.id_modo', 'IA_MODO.id_ia'], ondelete='RESTRICT'),
        db.UniqueConstraint('id_pipeline', 'nombre', 'orden', name='uk_pipeline_etapa_pipeline_nombre_orden')
    )
    
    modo = db.relationship('IAModo', primaryjoin="and_(PipelineEtapa.id_modo==IAModo.id_modo, PipelineEtapa.id_ia==IAModo.id_ia)")
    modelo = db.relationship('IAModelo', primaryjoin="PipelineEtapa.id_ia == IAModelo.id_ia", foreign_keys=[id_ia], viewonly=True)