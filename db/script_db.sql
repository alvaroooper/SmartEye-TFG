CREATE TABLE `USUARIO` (
    `id_usuario` INT NOT NULL AUTO_INCREMENT,
    `email` VARCHAR(255) NOT NULL,
    `username` VARCHAR(100) NOT NULL,
    `password_hash` VARCHAR(255) NOT NULL,
    `nombre_visible` VARCHAR(150) NULL,
    `estado_cuenta` VARCHAR(50) NOT NULL DEFAULT 'activa',
    `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `actualizado_en` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `borrado_en` DATETIME NULL,
    PRIMARY KEY (`id_usuario`),
    UNIQUE KEY `uk_usuario_email` (`email`),
    UNIQUE KEY `uk_usuario_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE `ROL` (
    `id_rol` INT NOT NULL AUTO_INCREMENT,
    `nombre` VARCHAR(100) NOT NULL,
    `descripcion` TEXT NULL,
    PRIMARY KEY (`id_rol`),
    UNIQUE KEY `uk_rol_nombre` (`nombre`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE `USUARIO_ROL` (
    `id_usuario` INT NOT NULL,
    `id_rol` INT NOT NULL,
    PRIMARY KEY (`id_usuario`, `id_rol`),
    CONSTRAINT `fk_usuario_rol_usuario`
        FOREIGN KEY (`id_usuario`) REFERENCES `USUARIO` (`id_usuario`)
        ON DELETE CASCADE
        ON UPDATE RESTRICT,
    CONSTRAINT `fk_usuario_rol_rol`
        FOREIGN KEY (`id_rol`) REFERENCES `ROL` (`id_rol`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE `TIPO_PLAN` (
    `id_plan` INT NOT NULL AUTO_INCREMENT,
    `nombre` VARCHAR(100) NOT NULL,
    `precio_mensual` DECIMAL(10,2) NULL,
    `habilitado` BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (`id_plan`),
    UNIQUE KEY `uk_tipo_plan_nombre` (`nombre`),
    CONSTRAINT `chk_tipo_plan_precio_mensual_no_negativo`
        CHECK (`precio_mensual` IS NULL OR `precio_mensual` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `SUSCRIPCION_PLAN` (
    `id_suscripcion` INT NOT NULL AUTO_INCREMENT,
    `id_usuario` INT NOT NULL,
    `id_plan` INT NOT NULL,
    `fecha_compra` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `fecha_inicio` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `fecha_fin` DATETIME NULL,
    `activo` BOOLEAN NOT NULL DEFAULT TRUE,
    `renovacion_auto` BOOLEAN NOT NULL DEFAULT FALSE,
    `importe` DECIMAL(10,2) NULL,
    `referencia_pago` VARCHAR(100) NULL,
    PRIMARY KEY (`id_suscripcion`),
    KEY `idx_suscripcion_plan_usuario` (`id_usuario`),
    KEY `idx_suscripcion_plan_plan` (`id_plan`),
    CONSTRAINT `fk_suscripcion_plan_usuario`
        FOREIGN KEY (`id_usuario`) REFERENCES `USUARIO` (`id_usuario`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `fk_suscripcion_plan_tipo_plan`
        FOREIGN KEY (`id_plan`) REFERENCES `TIPO_PLAN` (`id_plan`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `chk_suscripcion_plan_fechas_validas`
        CHECK (`fecha_fin` IS NULL OR `fecha_inicio` IS NULL OR `fecha_fin` >= `fecha_inicio`),
    CONSTRAINT `chk_suscripcion_plan_importe_no_negativo`
        CHECK (`importe` IS NULL OR `importe` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `IA_MODELO` (
    `id_ia` INT NOT NULL AUTO_INCREMENT,
    `nombre` VARCHAR(100) NOT NULL,
    `descripcion` TEXT NULL,
    `habilitada` BOOLEAN NOT NULL DEFAULT TRUE,
    `precio` DECIMAL(10,2) NULL,
    `ruta_servidor` VARCHAR(255) NULL,
    PRIMARY KEY (`id_ia`),
    UNIQUE KEY `uk_ia_modelo_nombre` (`nombre`),
    CONSTRAINT `chk_ia_modelo_precio_no_negativo`
        CHECK (`precio` IS NULL OR `precio` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE `IA_MODO` (
    `id_modo` INT NOT NULL AUTO_INCREMENT,
    `id_ia` INT NOT NULL,
    `nombre_modo` VARCHAR(100) NOT NULL,
    `descripcion` TEXT NULL,
    `habilitado` BOOLEAN NOT NULL DEFAULT TRUE,
    `config_predeterminada` TEXT NULL,
    PRIMARY KEY (`id_modo`),
    UNIQUE KEY `uk_ia_modo_id_modo_id_ia` (`id_modo`, `id_ia`),
    UNIQUE KEY `uk_ia_modo_nombre` (`id_ia`, `nombre_modo`),
    KEY `idx_ia_modo_ia` (`id_ia`),
    CONSTRAINT `fk_ia_modo_ia_modelo`
        FOREIGN KEY (`id_ia`) REFERENCES `IA_MODELO` (`id_ia`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE `ALQUILA` (
    `id_compra` INT NOT NULL AUTO_INCREMENT,
    `id_usuario` INT NOT NULL,
    `id_ia` INT NOT NULL,
    `fecha_compra` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `periodo_inicio` DATETIME NULL,
    `periodo_fin` DATETIME NULL,
    `activo` BOOLEAN NOT NULL DEFAULT TRUE,
    `renovacion_auto` BOOLEAN NOT NULL DEFAULT FALSE,
    `importe` DECIMAL(10,2) NULL,
    `referencia_pago` VARCHAR(100) NULL,
    PRIMARY KEY (`id_compra`),
    KEY `idx_alquila_usuario` (`id_usuario`),
    KEY `idx_alquila_ia` (`id_ia`),
    CONSTRAINT `fk_alquila_usuario`
        FOREIGN KEY (`id_usuario`) REFERENCES `USUARIO` (`id_usuario`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `fk_alquila_ia_modelo`
        FOREIGN KEY (`id_ia`) REFERENCES `IA_MODELO` (`id_ia`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `chk_alquila_importe_no_negativo`
        CHECK (`importe` IS NULL OR `importe` >= 0),
    CONSTRAINT `chk_alquila_periodo_valido`
        CHECK (`periodo_fin` IS NULL OR `periodo_inicio` IS NULL OR `periodo_fin` >= `periodo_inicio`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE `PIPELINE` (
    `id_pipeline` INT NOT NULL AUTO_INCREMENT,
    `id_usuario` INT NULL,
    `nombre` VARCHAR(100) NOT NULL,
    `descripcion` TEXT NULL,
    `habilitado` BOOLEAN NOT NULL DEFAULT TRUE,
    `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id_pipeline`),
    UNIQUE KEY `uk_pipeline_usuario_nombre` (`id_usuario`, `nombre`),
    KEY `idx_pipeline_usuario` (`id_usuario`),
    CONSTRAINT `fk_pipeline_usuario`
        FOREIGN KEY (`id_usuario`) REFERENCES `USUARIO` (`id_usuario`)
        ON DELETE SET NULL
        ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



CREATE TABLE `EJECUCION` (
    `id_ejecucion` INT NOT NULL AUTO_INCREMENT,
    `id_usuario` INT NOT NULL,
    `id_pipeline` INT NOT NULL,
    `origen` VARCHAR(100) NULL,
    `estado` VARCHAR(50) NOT NULL DEFAULT 'pendiente',
    `duracion_ms` INT NULL,
    `mensaje_error_user` TEXT NULL,
    `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `config_aplicada` TEXT NULL,
    PRIMARY KEY (`id_ejecucion`),
    KEY `idx_ejecucion_usuario` (`id_usuario`),
    KEY `idx_ejecucion_pipeline` (`id_pipeline`),
    CONSTRAINT `fk_ejecucion_usuario`
        FOREIGN KEY (`id_usuario`) REFERENCES `USUARIO` (`id_usuario`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `fk_ejecucion_pipeline`
        FOREIGN KEY (`id_pipeline`) REFERENCES `PIPELINE` (`id_pipeline`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `chk_ejecucion_duracion_no_negativa`
        CHECK (`duracion_ms` IS NULL OR `duracion_ms` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE `TEMPORAL_ARCHIVO` (
    `id_temporal` INT NOT NULL AUTO_INCREMENT,
    `id_ejecucion` INT NOT NULL,
    `tipo` VARCHAR(50) NULL,
    `ruta_servidor` VARCHAR(255) NULL,
    `token_descarga` VARCHAR(255) NULL,
    `expira_en` DATETIME NULL,
    PRIMARY KEY (`id_temporal`),
    UNIQUE KEY `uk_temporal_archivo_token_descarga` (`token_descarga`),
    KEY `idx_temporal_archivo_ejecucion` (`id_ejecucion`),
    CONSTRAINT `fk_temporal_archivo_ejecucion`
        FOREIGN KEY (`id_ejecucion`) REFERENCES `EJECUCION` (`id_ejecucion`)
        ON DELETE CASCADE
        ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE `PIPELINE_ETAPA` (
    `id_etapa` INT NOT NULL AUTO_INCREMENT,
    `id_pipeline` INT NOT NULL,
    `id_modo` INT NOT NULL,
    `id_ia` INT NOT NULL,
    `orden` INT NOT NULL,
    `nombre` VARCHAR(100) NOT NULL,
    `descripcion` TEXT NULL,
    PRIMARY KEY (`id_etapa`),
    UNIQUE KEY `uk_pipeline_etapa_pipeline_nombre_orden` (`id_pipeline`, `nombre`, `orden`),
    KEY `idx_pipeline_etapa_pipeline` (`id_pipeline`),
    KEY `idx_pipeline_etapa_modo_ia` (`id_modo`, `id_ia`),
    CONSTRAINT `fk_pipeline_etapa_pipeline`
        FOREIGN KEY (`id_pipeline`) REFERENCES `PIPELINE` (`id_pipeline`)
        ON DELETE CASCADE
        ON UPDATE RESTRICT,
    CONSTRAINT `fk_pipeline_etapa_ia_modo`
        FOREIGN KEY (`id_modo`, `id_ia`) REFERENCES `IA_MODO` (`id_modo`, `id_ia`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `chk_pipeline_etapa_orden_positivo`
        CHECK (`orden` >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;