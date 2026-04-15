/*M!999999\- enable the sandbox mode */ 
-- MariaDB dump 10.19-11.8.6-MariaDB, for debian-linux-gnu (x86_64)
--
-- Host: localhost    Database: tfg_db
-- ------------------------------------------------------
-- Server version	11.8.6-MariaDB-0+deb13u1 from Debian

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*M!100616 SET @OLD_NOTE_VERBOSITY=@@NOTE_VERBOSITY, NOTE_VERBOSITY=0 */;

--
-- Table structure for table `ALQUILA`
--

DROP TABLE IF EXISTS `ALQUILA`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ALQUILA` (
  `id_compra` int(11) NOT NULL AUTO_INCREMENT,
  `id_usuario` int(11) NOT NULL,
  `id_ia` int(11) NOT NULL,
  `fecha_compra` datetime NOT NULL DEFAULT current_timestamp(),
  `periodo_inicio` datetime DEFAULT NULL,
  `periodo_fin` datetime DEFAULT NULL,
  `activo` tinyint(1) NOT NULL DEFAULT 0,
  `renovacion_auto` tinyint(1) NOT NULL DEFAULT 0,
  `importe` decimal(10,2) DEFAULT NULL,
  `referencia_pago` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`id_compra`),
  KEY `idx_alquila_usuario` (`id_usuario`),
  KEY `idx_alquila_ia` (`id_ia`),
  CONSTRAINT `fk_alquila_ia_modelo` FOREIGN KEY (`id_ia`) REFERENCES `IA_MODELO` (`id_ia`),
  CONSTRAINT `fk_alquila_usuario` FOREIGN KEY (`id_usuario`) REFERENCES `USUARIO` (`id_usuario`),
  CONSTRAINT `chk_alquila_importe_no_negativo` CHECK (`importe` is null or `importe` >= 0),
  CONSTRAINT `chk_alquila_periodo_valido` CHECK (`periodo_fin` is null or `periodo_inicio` is null or `periodo_fin` >= `periodo_inicio`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ALQUILA`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `ALQUILA` WRITE;
/*!40000 ALTER TABLE `ALQUILA` DISABLE KEYS */;
/*!40000 ALTER TABLE `ALQUILA` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `EJECUCION`
--

DROP TABLE IF EXISTS `EJECUCION`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `EJECUCION` (
  `id_ejecucion` int(11) NOT NULL AUTO_INCREMENT,
  `id_usuario` int(11) NOT NULL,
  `id_pipeline` int(11) NOT NULL,
  `origen` varchar(100) DEFAULT NULL,
  `estado` varchar(50) NOT NULL DEFAULT 'pendiente',
  `duracion_ms` int(11) DEFAULT NULL,
  `mensaje_error_user` text DEFAULT NULL,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  `config_aplicada` text DEFAULT NULL,
  PRIMARY KEY (`id_ejecucion`),
  KEY `idx_ejecucion_usuario` (`id_usuario`),
  KEY `idx_ejecucion_pipeline` (`id_pipeline`),
  CONSTRAINT `fk_ejecucion_pipeline` FOREIGN KEY (`id_pipeline`) REFERENCES `PIPELINE` (`id_pipeline`),
  CONSTRAINT `fk_ejecucion_usuario` FOREIGN KEY (`id_usuario`) REFERENCES `USUARIO` (`id_usuario`),
  CONSTRAINT `chk_ejecucion_duracion_no_negativa` CHECK (`duracion_ms` is null or `duracion_ms` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `EJECUCION`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `EJECUCION` WRITE;
/*!40000 ALTER TABLE `EJECUCION` DISABLE KEYS */;
/*!40000 ALTER TABLE `EJECUCION` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `IA_MODELO`
--

DROP TABLE IF EXISTS `IA_MODELO`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `IA_MODELO` (
  `id_ia` int(11) NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `descripcion` text DEFAULT NULL,
  `habilitada` tinyint(1) NOT NULL DEFAULT 1,
  `precio` decimal(10,2) DEFAULT NULL,
  `ruta_servidor` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id_ia`),
  UNIQUE KEY `uk_ia_modelo_nombre` (`nombre`),
  CONSTRAINT `chk_ia_modelo_precio_no_negativo` CHECK (`precio` is null or `precio` >= 0)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `IA_MODELO`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `IA_MODELO` WRITE;
/*!40000 ALTER TABLE `IA_MODELO` DISABLE KEYS */;
INSERT INTO `IA_MODELO` VALUES
(1,'MediaPipe','Detección de puntos clave corporales',1,NULL,'models/mediapipe/'),
(2,'yolo','Detección de objetos en tiempo real',1,NULL,'models/yolo/');
/*!40000 ALTER TABLE `IA_MODELO` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `IA_MODO`
--

DROP TABLE IF EXISTS `IA_MODO`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `IA_MODO` (
  `id_modo` int(11) NOT NULL AUTO_INCREMENT,
  `id_ia` int(11) NOT NULL,
  `nombre_modo` varchar(100) NOT NULL,
  `descripcion` text DEFAULT NULL,
  `habilitado` tinyint(1) NOT NULL DEFAULT 1,
  `config_predeterminada` text DEFAULT NULL,
  PRIMARY KEY (`id_modo`),
  UNIQUE KEY `uk_ia_modo_id_modo_id_ia` (`id_modo`,`id_ia`),
  UNIQUE KEY `uk_ia_modo_nombre` (`id_ia`,`nombre_modo`),
  KEY `idx_ia_modo_ia` (`id_ia`),
  CONSTRAINT `fk_ia_modo_ia_modelo` FOREIGN KEY (`id_ia`) REFERENCES `IA_MODELO` (`id_ia`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `IA_MODO`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `IA_MODO` WRITE;
/*!40000 ALTER TABLE `IA_MODO` DISABLE KEYS */;
INSERT INTO `IA_MODO` VALUES
(1,1,'manos','Seguimiento de manos',1,NULL),
(2,1,'pose','Seguimiento de cuerpo completo',1,NULL),
(3,2,'deteccion','Detección de 80 clases de objetos',1,NULL);
/*!40000 ALTER TABLE `IA_MODO` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `PIPELINE`
--

DROP TABLE IF EXISTS `PIPELINE`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `PIPELINE` (
  `id_pipeline` int(11) NOT NULL AUTO_INCREMENT,
  `id_usuario` int(11) DEFAULT NULL,
  `nombre` varchar(100) NOT NULL,
  `descripcion` text DEFAULT NULL,
  `habilitado` tinyint(1) NOT NULL DEFAULT 1,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id_pipeline`),
  UNIQUE KEY `uk_pipeline_usuario_nombre` (`id_usuario`,`nombre`),
  KEY `idx_pipeline_usuario` (`id_usuario`),
  CONSTRAINT `fk_pipeline_usuario` FOREIGN KEY (`id_usuario`) REFERENCES `USUARIO` (`id_usuario`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `PIPELINE`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `PIPELINE` WRITE;
/*!40000 ALTER TABLE `PIPELINE` DISABLE KEYS */;
INSERT INTO `PIPELINE` VALUES
(1,1,'Analisis Completo','Pipeline que usa Pose y Objetos',1,'2026-04-08 20:15:13'),
(2,1,'Solo Manos','Pipeline rápido de MediaPipe Hands',1,'2026-04-08 20:15:13');
/*!40000 ALTER TABLE `PIPELINE` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `PIPELINE_ETAPA`
--

DROP TABLE IF EXISTS `PIPELINE_ETAPA`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `PIPELINE_ETAPA` (
  `id_etapa` int(11) NOT NULL AUTO_INCREMENT,
  `id_pipeline` int(11) NOT NULL,
  `id_modo` int(11) NOT NULL,
  `id_ia` int(11) NOT NULL,
  `orden` int(11) NOT NULL,
  `nombre` varchar(100) NOT NULL,
  `descripcion` text DEFAULT NULL,
  PRIMARY KEY (`id_etapa`),
  UNIQUE KEY `uk_pipeline_etapa_pipeline_nombre_orden` (`id_pipeline`,`nombre`,`orden`),
  KEY `idx_pipeline_etapa_pipeline` (`id_pipeline`),
  KEY `idx_pipeline_etapa_modo_ia` (`id_modo`,`id_ia`),
  CONSTRAINT `fk_pipeline_etapa_ia_modo` FOREIGN KEY (`id_modo`, `id_ia`) REFERENCES `IA_MODO` (`id_modo`, `id_ia`),
  CONSTRAINT `fk_pipeline_etapa_pipeline` FOREIGN KEY (`id_pipeline`) REFERENCES `PIPELINE` (`id_pipeline`) ON DELETE CASCADE,
  CONSTRAINT `chk_pipeline_etapa_orden_positivo` CHECK (`orden` >= 1)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `PIPELINE_ETAPA`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `PIPELINE_ETAPA` WRITE;
/*!40000 ALTER TABLE `PIPELINE_ETAPA` DISABLE KEYS */;
INSERT INTO `PIPELINE_ETAPA` VALUES
(1,1,2,1,1,'Extraccion Pose',NULL),
(2,1,3,2,2,'Deteccion Objetos',NULL),
(3,2,1,1,1,'Tracking Manos',NULL);
/*!40000 ALTER TABLE `PIPELINE_ETAPA` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `ROL`
--

DROP TABLE IF EXISTS `ROL`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ROL` (
  `id_rol` int(11) NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `descripcion` text DEFAULT NULL,
  PRIMARY KEY (`id_rol`),
  UNIQUE KEY `uk_rol_nombre` (`nombre`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ROL`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `ROL` WRITE;
/*!40000 ALTER TABLE `ROL` DISABLE KEYS */;
INSERT INTO `ROL` VALUES
(1,'admin','Administrador total del sistema'),
(2,'usuario','Usuario estándar con acceso a funciones básicas');
/*!40000 ALTER TABLE `ROL` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `SUSCRIPCION_PLAN`
--

DROP TABLE IF EXISTS `SUSCRIPCION_PLAN`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `SUSCRIPCION_PLAN` (
  `id_suscripcion` int(11) NOT NULL AUTO_INCREMENT,
  `id_usuario` int(11) NOT NULL,
  `id_plan` int(11) NOT NULL,
  `fecha_compra` datetime NOT NULL DEFAULT current_timestamp(),
  `fecha_inicio` datetime NOT NULL DEFAULT current_timestamp(),
  `fecha_fin` datetime DEFAULT NULL,
  `activo` tinyint(1) NOT NULL DEFAULT 1,
  `renovacion_auto` tinyint(1) NOT NULL DEFAULT 0,
  `importe` decimal(10,2) DEFAULT NULL,
  `referencia_pago` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`id_suscripcion`),
  KEY `idx_suscripcion_plan_usuario` (`id_usuario`),
  KEY `idx_suscripcion_plan_plan` (`id_plan`),
  CONSTRAINT `fk_suscripcion_plan_tipo_plan` FOREIGN KEY (`id_plan`) REFERENCES `TIPO_PLAN` (`id_plan`),
  CONSTRAINT `fk_suscripcion_plan_usuario` FOREIGN KEY (`id_usuario`) REFERENCES `USUARIO` (`id_usuario`),
  CONSTRAINT `chk_suscripcion_plan_fechas_validas` CHECK (`fecha_fin` is null or `fecha_inicio` is null or `fecha_fin` >= `fecha_inicio`),
  CONSTRAINT `chk_suscripcion_plan_importe_no_negativo` CHECK (`importe` is null or `importe` >= 0)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `SUSCRIPCION_PLAN`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `SUSCRIPCION_PLAN` WRITE;
/*!40000 ALTER TABLE `SUSCRIPCION_PLAN` DISABLE KEYS */;
INSERT INTO `SUSCRIPCION_PLAN` VALUES
(1,1,2,'2026-04-08 20:15:13','2026-04-08 20:15:13',NULL,1,0,19.99,NULL),
(2,2,1,'2026-04-08 20:15:13','2026-04-08 20:15:13',NULL,1,0,0.00,NULL);
/*!40000 ALTER TABLE `SUSCRIPCION_PLAN` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `TEMPORAL_ARCHIVO`
--

DROP TABLE IF EXISTS `TEMPORAL_ARCHIVO`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `TEMPORAL_ARCHIVO` (
  `id_temporal` int(11) NOT NULL AUTO_INCREMENT,
  `id_ejecucion` int(11) NOT NULL,
  `tipo` varchar(50) DEFAULT NULL,
  `ruta_servidor` varchar(255) DEFAULT NULL,
  `token_descarga` varchar(255) DEFAULT NULL,
  `expira_en` datetime DEFAULT NULL,
  PRIMARY KEY (`id_temporal`),
  UNIQUE KEY `uk_temporal_archivo_token_descarga` (`token_descarga`),
  KEY `idx_temporal_archivo_ejecucion` (`id_ejecucion`),
  CONSTRAINT `fk_temporal_archivo_ejecucion` FOREIGN KEY (`id_ejecucion`) REFERENCES `EJECUCION` (`id_ejecucion`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `TEMPORAL_ARCHIVO`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `TEMPORAL_ARCHIVO` WRITE;
/*!40000 ALTER TABLE `TEMPORAL_ARCHIVO` DISABLE KEYS */;
/*!40000 ALTER TABLE `TEMPORAL_ARCHIVO` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `TIPO_PLAN`
--

DROP TABLE IF EXISTS `TIPO_PLAN`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `TIPO_PLAN` (
  `id_plan` int(11) NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `precio_mensual` decimal(10,2) DEFAULT NULL,
  `habilitado` tinyint(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id_plan`),
  UNIQUE KEY `uk_tipo_plan_nombre` (`nombre`),
  CONSTRAINT `chk_tipo_plan_precio_mensual_no_negativo` CHECK (`precio_mensual` is null or `precio_mensual` >= 0)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `TIPO_PLAN`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `TIPO_PLAN` WRITE;
/*!40000 ALTER TABLE `TIPO_PLAN` DISABLE KEYS */;
INSERT INTO `TIPO_PLAN` VALUES
(1,'Basico',0.00,1),
(2,'Pro',19.99,1);
/*!40000 ALTER TABLE `TIPO_PLAN` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `USUARIO`
--

DROP TABLE IF EXISTS `USUARIO`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `USUARIO` (
  `id_usuario` int(11) NOT NULL AUTO_INCREMENT,
  `email` varchar(255) NOT NULL,
  `username` varchar(100) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `nombre_visible` varchar(150) DEFAULT NULL,
  `estado_cuenta` varchar(50) NOT NULL DEFAULT 'activa',
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  `actualizado_en` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `borrado_en` datetime DEFAULT NULL,
  PRIMARY KEY (`id_usuario`),
  UNIQUE KEY `uk_usuario_email` (`email`),
  UNIQUE KEY `uk_usuario_username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `USUARIO`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `USUARIO` WRITE;
/*!40000 ALTER TABLE `USUARIO` DISABLE KEYS */;
INSERT INTO `USUARIO` VALUES
(1,'admin@tfg.es','admin','scrypt:32768:8:1$mkyXNH40U5qgEduf$8ee2d7fda7766aa028ea86c60b524d77f43436497a00ebac7fca607076cf65bb60e9cbbb2f88eec8fd2f8ae687ca1a09cab0daebee5cde5d386911da8e3f7ea9','Administrador TFG','activa','2026-04-08 20:15:12','2026-04-08 16:37:50',NULL),
(2,'test@tfg.es','alvaro','scrypt:32768:8:1$unA6wsWB7niQrMsA$27c87036b98390da7cdfb29af7e89e06c050f7cbbe8f1cc2f5764c0c8d3e87460f68dd4fb2d322b4b92e3a15e1c6577b9c019fb02543def3a75f61fac11a7b1c','Alvaro Perez','activa','2026-04-08 20:15:12','2026-04-08 16:37:50',NULL),
(3,'pepito@gmail.com','pepito','scrypt:32768:8:1$d80aJDMLBNbspTeW$1f7d6b463d55b1c65036d61fc24c40078a59c66a528dea53e7bcebfd51322ff07056f93768a8b31a7ab81cd9e5a7fdecaae96805451fe3140d1e321929755b28','Pepe Pérez','activa','2026-04-15 18:22:21','2026-04-15 16:22:21',NULL);
/*!40000 ALTER TABLE `USUARIO` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `USUARIO_ROL`
--

DROP TABLE IF EXISTS `USUARIO_ROL`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `USUARIO_ROL` (
  `id_usuario` int(11) NOT NULL,
  `id_rol` int(11) NOT NULL,
  PRIMARY KEY (`id_usuario`,`id_rol`),
  KEY `fk_usuario_rol_rol` (`id_rol`),
  CONSTRAINT `fk_usuario_rol_rol` FOREIGN KEY (`id_rol`) REFERENCES `ROL` (`id_rol`),
  CONSTRAINT `fk_usuario_rol_usuario` FOREIGN KEY (`id_usuario`) REFERENCES `USUARIO` (`id_usuario`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `USUARIO_ROL`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `USUARIO_ROL` WRITE;
/*!40000 ALTER TABLE `USUARIO_ROL` DISABLE KEYS */;
INSERT INTO `USUARIO_ROL` VALUES
(1,1),
(2,2),
(3,2);
/*!40000 ALTER TABLE `USUARIO_ROL` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Dumping routines for database 'tfg_db'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*M!100616 SET NOTE_VERBOSITY=@OLD_NOTE_VERBOSITY */;

-- Dump completed on 2026-04-15 21:42:00
