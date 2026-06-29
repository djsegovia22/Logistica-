-- ══════════════════════════════════════════════════════════════
--  DSG Ingeniería — Sistema de Solicitudes
--  Base de datos: MySQL / MariaDB
--  Solo tablas (sin datos)
-- ══════════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS dsg_solicitudes
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE dsg_solicitudes;

-- ──────────────────────────────────────────────────────────────
--  USUARIOS
--  Roles: superadmin, admin
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usuarios (
  id          INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  username    VARCHAR(80)     NOT NULL,
  password    CHAR(64)        NOT NULL COMMENT 'SHA-256 del password',
  rol         ENUM('superadmin','admin') NOT NULL DEFAULT 'admin',
  creado_en   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  UNIQUE KEY uq_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ──────────────────────────────────────────────────────────────
--  SOLICITUDES
--  Las envian personas externas sin login
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS solicitudes (
  id           BIGINT UNSIGNED NOT NULL,
  nombre       VARCHAR(120)    NOT NULL COMMENT 'Nombre y apellido del solicitante',
  tipo         VARCHAR(80)     NOT NULL,
  descripcion  TEXT            NOT NULL,
  prioridad    ENUM('Normal','Alta','Urgente') NOT NULL DEFAULT 'Normal',
  estado       ENUM('Pendiente','En proceso','Resuelto') NOT NULL DEFAULT 'Pendiente',
  asignado_a   VARCHAR(80)     NULL     COMMENT 'username del admin asignado',
  fecha        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  KEY idx_estado     (estado),
  KEY idx_asignado   (asignado_a),
  KEY idx_fecha      (fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ──────────────────────────────────────────────────────────────
--  CONFIGURACION WHATSAPP (CallMeBot)
--  Solo una fila
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wa_config (
  id      TINYINT UNSIGNED NOT NULL DEFAULT 1,
  phone   VARCHAR(20)      NOT NULL DEFAULT '',
  apikey  VARCHAR(40)      NOT NULL DEFAULT '',

  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
