"""
Script de inicialización de la base de datos local.
Crea todas las tablas necesarias y un usuario administrador por defecto.

Uso:
    .venv/Scripts/python.exe setup_local_db.py

Usuario admin creado:
    usuario:    admin
    contraseña: admin123
"""

import mysql.connector
import bcrypt
import sys
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Configuración ──────────────────────────────────────────────────────────
HOST     = os.getenv('MYSQL_HOST', '127.0.0.1')
PORT     = int(os.getenv('MYSQL_PORT', 3306))
USER     = os.getenv('MYSQL_USER', 'root')
PASSWORD = os.getenv('MYSQL_PASSWORD', 'root')
DATABASE = os.getenv('MYSQL_DATABASE', 'elite_bike_db')

ADMIN_USUARIO    = 'admin'
ADMIN_NOMBRE     = 'Administrador'
ADMIN_CORREO     = 'admin@elitebike.com'
ADMIN_CONTRASENA = 'admin123'


def conectar(database=None):
    cfg = dict(host=HOST, port=PORT, user=USER, password=PASSWORD)
    if database:
        cfg['database'] = database
    return mysql.connector.connect(**cfg)


def crear_base_de_datos(conn):
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    conn.commit()
    cur.close()
    print(f"[OK] Base de datos '{DATABASE}' lista.")


TABLAS = [
    # ── Auth / usuarios ───────────────────────────────────────────────────────
    ("roles", """
        CREATE TABLE IF NOT EXISTS roles (
            id   INT AUTO_INCREMENT PRIMARY KEY,
            nombre VARCHAR(50) NOT NULL UNIQUE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("grupo_clientes", """
        CREATE TABLE IF NOT EXISTS grupo_clientes (
            id           INT AUTO_INCREMENT PRIMARY KEY,
            nombre_grupo VARCHAR(200) NOT NULL UNIQUE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("clientes", """
        CREATE TABLE IF NOT EXISTS clientes (
            id             INT AUTO_INCREMENT PRIMARY KEY,
            clave          VARCHAR(50),
            evac           VARCHAR(10),
            nombre_cliente VARCHAR(300),
            nivel          VARCHAR(100),
            f_inicio       DATE,
            f_fin          DATE,
            id_grupo       INT,
            FOREIGN KEY (id_grupo) REFERENCES grupo_clientes(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("usuarios", """
        CREATE TABLE IF NOT EXISTS usuarios (
            id                 INT AUTO_INCREMENT PRIMARY KEY,
            usuario            VARCHAR(50)  NOT NULL UNIQUE,
            contrasena         VARCHAR(255) NOT NULL,
            nombre             VARCHAR(200),
            correo             VARCHAR(200) UNIQUE,
            rol_id             INT DEFAULT 2,
            activo             TINYINT(1) DEFAULT 1,
            cliente_id         INT,
            flujo              TINYINT(1) DEFAULT 0,
            token              VARCHAR(500),
            codigo_activacion  VARCHAR(10),
            token_correo       VARCHAR(100),
            token_expiracion   DATETIME,
            FOREIGN KEY (rol_id)     REFERENCES roles(id),
            FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    # ── Catálogo de distribuidores / metas ────────────────────────────────────
    ("niveles_distribuidor", """
        CREATE TABLE IF NOT EXISTS niveles_distribuidor (
            id                   INT AUTO_INCREMENT PRIMARY KEY,
            nivel                VARCHAR(100),
            compromiso_scott     DECIMAL(15,2) DEFAULT 0,
            compromiso_syncros   DECIMAL(15,2) DEFAULT 0,
            compromiso_apparel   DECIMAL(15,2) DEFAULT 0,
            compromiso_vittoria  DECIMAL(15,2) DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    # ── Monitor de ventas (sincronización Odoo) ───────────────────────────────
    ("monitor", """
        CREATE TABLE IF NOT EXISTS monitor (
            id                   INT AUTO_INCREMENT PRIMARY KEY,
            numero_factura       VARCHAR(100),
            referencia_interna   VARCHAR(255),
            nombre_producto      VARCHAR(400),
            contacto_referencia  VARCHAR(200),
            contacto_nombre      VARCHAR(300),
            fecha_factura        DATE,
            precio_unitario      DECIMAL(15,2),
            cantidad             DECIMAL(12,4),
            venta_total          DECIMAL(15,2),
            marca                VARCHAR(100),
            subcategoria         VARCHAR(200),
            apparel              TINYINT(1) DEFAULT 0,
            eride                TINYINT(1) DEFAULT 0,
            evac                 VARCHAR(10),
            categoria_producto   VARCHAR(200),
            estado_factura       VARCHAR(50),
            INDEX idx_fecha          (fecha_factura),
            INDEX idx_referencia     (referencia_interna),
            INDEX idx_contacto_ref   (contacto_referencia)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("historial_actualizaciones", """
        CREATE TABLE IF NOT EXISTS historial_actualizaciones (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            fecha_actualizacion DATETIME NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("cache_ultima_actualizacion", """
        CREATE TABLE IF NOT EXISTS cache_ultima_actualizacion (
            id           INT PRIMARY KEY DEFAULT 1,
            ultima_fecha DATETIME
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    # ── Previo ────────────────────────────────────────────────────────────────
    ("previo", """
        CREATE TABLE IF NOT EXISTS previo (
            id                                       INT AUTO_INCREMENT PRIMARY KEY,
            clave                                    VARCHAR(50),
            evac                                     VARCHAR(10),
            nombre_cliente                           VARCHAR(300),
            acumulado_anticipado                     DECIMAL(15,2) DEFAULT 0,
            nivel                                    VARCHAR(100),
            nivel_cierre_compra_inicial              VARCHAR(100),
            compra_minima_anual                      DECIMAL(15,2) DEFAULT 0,
            porcentaje_anual                         INT DEFAULT 0,
            compra_minima_inicial                    DECIMAL(15,2) DEFAULT 0,
            avance_global                            DECIMAL(15,2) DEFAULT 0,
            porcentaje_global                        INT DEFAULT 0,
            compromiso_scott                         DECIMAL(15,2) DEFAULT 0,
            avance_global_scott                      DECIMAL(15,2) DEFAULT 0,
            porcentaje_scott                         INT DEFAULT 0,
            compromiso_jul_ago                       DECIMAL(15,2) DEFAULT 0,
            avance_jul_ago                           DECIMAL(15,2) DEFAULT 0,
            porcentaje_jul_ago                       INT DEFAULT 0,
            compromiso_sep_oct                       DECIMAL(15,2) DEFAULT 0,
            avance_sep_oct                           DECIMAL(15,2) DEFAULT 0,
            porcentaje_sep_oct                       INT DEFAULT 0,
            compromiso_nov_dic                       DECIMAL(15,2) DEFAULT 0,
            avance_nov_dic                           DECIMAL(15,2) DEFAULT 0,
            porcentaje_nov_dic                       INT DEFAULT 0,
            compromiso_ene_feb                       DECIMAL(15,2) DEFAULT 0,
            avance_ene_feb                           DECIMAL(15,2) DEFAULT 0,
            porcentaje_ene_feb                       INT DEFAULT 0,
            compromiso_mar_abr                       DECIMAL(15,2) DEFAULT 0,
            avance_mar_abr                           DECIMAL(15,2) DEFAULT 0,
            porcentaje_mar_abr                       INT DEFAULT 0,
            compromiso_may_jun                       DECIMAL(15,2) DEFAULT 0,
            avance_may_jun                           DECIMAL(15,2) DEFAULT 0,
            porcentaje_may_jun                       INT DEFAULT 0,
            compromiso_apparel_syncros_vittoria      DECIMAL(15,2) DEFAULT 0,
            avance_global_apparel_syncros_vittoria   DECIMAL(15,2) DEFAULT 0,
            porcentaje_apparel_syncros_vittoria      INT DEFAULT 0,
            compromiso_jul_ago_app                   DECIMAL(15,2) DEFAULT 0,
            avance_jul_ago_app                       DECIMAL(15,2) DEFAULT 0,
            porcentaje_jul_ago_app                   INT DEFAULT 0,
            compromiso_sep_oct_app                   DECIMAL(15,2) DEFAULT 0,
            avance_sep_oct_app                       DECIMAL(15,2) DEFAULT 0,
            porcentaje_sep_oct_app                   INT DEFAULT 0,
            compromiso_nov_dic_app                   DECIMAL(15,2) DEFAULT 0,
            avance_nov_dic_app                       DECIMAL(15,2) DEFAULT 0,
            porcentaje_nov_dic_app                   INT DEFAULT 0,
            compromiso_ene_feb_app                   DECIMAL(15,2) DEFAULT 0,
            avance_ene_feb_app                       DECIMAL(15,2) DEFAULT 0,
            porcentaje_ene_feb_app                   INT DEFAULT 0,
            compromiso_mar_abr_app                   DECIMAL(15,2) DEFAULT 0,
            avance_mar_abr_app                       DECIMAL(15,2) DEFAULT 0,
            porcentaje_mar_abr_app                   INT DEFAULT 0,
            compromiso_may_jun_app                   DECIMAL(15,2) DEFAULT 0,
            avance_may_jun_app                       DECIMAL(15,2) DEFAULT 0,
            porcentaje_may_jun_app                   INT DEFAULT 0,
            acumulado_syncros                        DECIMAL(15,2) DEFAULT 0,
            acumulado_apparel                        DECIMAL(15,2) DEFAULT 0,
            acumulado_vittoria                       DECIMAL(15,2) DEFAULT 0,
            acumulado_bold                           DECIMAL(15,2) DEFAULT 0,
            es_integral                              TINYINT(1) DEFAULT 0,
            grupo_integral                           VARCHAR(100)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    # ── Carátulas ─────────────────────────────────────────────────────────────
    ("caratula_evac_a", """
        CREATE TABLE IF NOT EXISTS caratula_evac_a (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            categoria           VARCHAR(200),
            meta                DECIMAL(15,2) DEFAULT 0,
            acumulado_real      DECIMAL(15,2) DEFAULT 0,
            avance_proyectado   DECIMAL(15,2) DEFAULT 0,
            porcentaje          DECIMAL(8,4)  DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("caratula_evac_b", """
        CREATE TABLE IF NOT EXISTS caratula_evac_b (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            categoria           VARCHAR(200),
            meta                DECIMAL(15,2) DEFAULT 0,
            acumulado_real      DECIMAL(15,2) DEFAULT 0,
            avance_proyectado   DECIMAL(15,2) DEFAULT 0,
            porcentaje          DECIMAL(8,4)  DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("historial_caratulas", """
        CREATE TABLE IF NOT EXISTS historial_caratulas (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            nombre_usuario      VARCHAR(200),
            usuario_envio       VARCHAR(100),
            correo_remitente    VARCHAR(200),
            correo_destinatario VARCHAR(200),
            cliente_nombre      VARCHAR(300),
            clave_cliente       VARCHAR(50),
            fecha_envio         DATE,
            hora_envio          TIME,
            estado              VARCHAR(50)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    # ── Proyecciones (sistema legacy) ─────────────────────────────────────────
    ("disponibilidad_proyeccion", """
        CREATE TABLE IF NOT EXISTS disponibilidad_proyeccion (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            q1_oct_2025 TINYINT(1) DEFAULT 0,
            q2_oct_2025 TINYINT(1) DEFAULT 0,
            q1_nov_2025 TINYINT(1) DEFAULT 0,
            q2_nov_2025 TINYINT(1) DEFAULT 0,
            q1_dic_2025 TINYINT(1) DEFAULT 0,
            q2_dic_2025 TINYINT(1) DEFAULT 0,
            descripcion VARCHAR(500)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("proyecciones_ventas", """
        CREATE TABLE IF NOT EXISTS proyecciones_ventas (
            id                           INT AUTO_INCREMENT PRIMARY KEY,
            referencia                   VARCHAR(100),
            clave_factura                VARCHAR(100),
            clave_6_digitos              VARCHAR(50),
            ean                          VARCHAR(50),
            clave_odoo                   VARCHAR(100),
            descripcion                  VARCHAR(400),
            modelo                       VARCHAR(200),
            spec                         VARCHAR(200),
            precio_elite_plus_sin_iva    DECIMAL(15,2) DEFAULT 0,
            precio_elite_plus_con_iva    DECIMAL(15,2) DEFAULT 0,
            precio_elite_sin_iva         DECIMAL(15,2) DEFAULT 0,
            precio_elite_con_iva         DECIMAL(15,2) DEFAULT 0,
            precio_partner_sin_iva       DECIMAL(15,2) DEFAULT 0,
            precio_partner_con_iva       DECIMAL(15,2) DEFAULT 0,
            precio_distribuidor_sin_iva  DECIMAL(15,2) DEFAULT 0,
            precio_distribuidor_con_iva  DECIMAL(15,2) DEFAULT 0,
            precio_publico_sin_iva       DECIMAL(15,2) DEFAULT 0,
            precio_publico_con_iva       DECIMAL(15,2) DEFAULT 0,
            precio_publico_con_iva_my26  DECIMAL(15,2) DEFAULT 0,
            q1_sep_2025                  INT DEFAULT 0,
            q2_sep_2025                  INT DEFAULT 0,
            q1_oct_2025                  INT DEFAULT 0,
            q2_oct_2025                  INT DEFAULT 0,
            q1_nov_2025                  INT DEFAULT 0,
            q2_nov_2025                  INT DEFAULT 0,
            q1_dic_2025                  INT DEFAULT 0,
            q2_dic_2025                  INT DEFAULT 0,
            q1_mar_2026                  INT DEFAULT 0,
            q2_mar_2026                  INT DEFAULT 0,
            q1_abr_2026                  INT DEFAULT 0,
            q2_abr_2026                  INT DEFAULT 0,
            q1_may_2026                  INT DEFAULT 0,
            q2_may_2026                  INT DEFAULT 0,
            id_disponibilidad            INT,
            FOREIGN KEY (id_disponibilidad) REFERENCES disponibilidad_proyeccion(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("proyecciones_cliente", """
        CREATE TABLE IF NOT EXISTS proyecciones_cliente (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            id_cliente      INT NOT NULL,
            id_proyeccion   INT NOT NULL,
            precio_aplicado DECIMAL(15,2) DEFAULT 0,
            folio           VARCHAR(50),
            q1_sep_2025     INT DEFAULT 0,
            q2_sep_2025     INT DEFAULT 0,
            q1_oct_2025     INT DEFAULT 0,
            q2_oct_2025     INT DEFAULT 0,
            q1_nov_2025     INT DEFAULT 0,
            q2_nov_2025     INT DEFAULT 0,
            q1_dic_2025     INT DEFAULT 0,
            q2_dic_2025     INT DEFAULT 0,
            q1_mar_2026     INT DEFAULT 0,
            q2_mar_2026     INT DEFAULT 0,
            q1_abr_2026     INT DEFAULT 0,
            q2_abr_2026     INT DEFAULT 0,
            q1_may_2026     INT DEFAULT 0,
            q2_may_2026     INT DEFAULT 0,
            creado_en       DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("proyecciones_autoguardado", """
        CREATE TABLE IF NOT EXISTS proyecciones_autoguardado (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            id_cliente          INT NOT NULL,
            id_proyeccion       INT NOT NULL,
            q1_sep_2025         INT DEFAULT 0,
            q2_sep_2025         INT DEFAULT 0,
            q1_oct_2025         INT DEFAULT 0,
            q2_oct_2025         INT DEFAULT 0,
            q1_nov_2025         INT DEFAULT 0,
            q2_nov_2025         INT DEFAULT 0,
            q1_dic_2025         INT DEFAULT 0,
            q2_dic_2025         INT DEFAULT 0,
            q1_mar_2026         INT DEFAULT 0,
            q2_mar_2026         INT DEFAULT 0,
            q1_abr_2026         INT DEFAULT 0,
            q2_abr_2026         INT DEFAULT 0,
            q1_may_2026         INT DEFAULT 0,
            q2_may_2026         INT DEFAULT 0,
            fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_autoguardado (id_cliente, id_proyeccion)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    # ── Flujo de efectivo ─────────────────────────────────────────────────────
    ("ordenes_compra", """
        CREATE TABLE IF NOT EXISTS ordenes_compra (
            id_orden          INT AUTO_INCREMENT PRIMARY KEY,
            codigo_po         VARCHAR(100),
            proveedor         VARCHAR(200),
            fecha_po          DATE,
            moneda            VARCHAR(10) DEFAULT 'MXN',
            importe_original  DECIMAL(15,2),
            importe_final     DECIMAL(15,2),
            fecha_vencimiento DATE,
            estatus           VARCHAR(50) DEFAULT 'PRODUCCION',
            created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("embarques_logistica", """
        CREATE TABLE IF NOT EXISTS embarques_logistica (
            id_embarque           INT AUTO_INCREMENT PRIMARY KEY,
            codigo_embarque       VARCHAR(100),
            orden_compra_id       INT,
            contenedor            VARCHAR(100),
            fecha_eta             DATE,
            tipo_cambio_proy      DECIMAL(10,4) DEFAULT 19.50,
            valor_aduana_mxn      DECIMAL(15,2) DEFAULT 0,
            pago_igi              DECIMAL(15,2) DEFAULT 0,
            pago_dta              DECIMAL(15,2) DEFAULT 0,
            pago_iva_impo         DECIMAL(15,2) DEFAULT 0,
            gasto_flete_mxn       DECIMAL(15,2) DEFAULT 0,
            fecha_pago_impuestos  DATE,
            created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (orden_compra_id) REFERENCES ordenes_compra(id_orden) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("ingresos_cobranza", """
        CREATE TABLE IF NOT EXISTS ingresos_cobranza (
            id                   INT AUTO_INCREMENT PRIMARY KEY,
            folio_factura        VARCHAR(100),
            cliente              VARCHAR(300),
            fecha_promesa_pago   DATE,
            monto_cobro          DECIMAL(15,2),
            probabilidad         VARCHAR(20) DEFAULT 'ALTA',
            cuenta_destino       VARCHAR(200),
            estatus              VARCHAR(30) DEFAULT 'PENDIENTE',
            created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("cat_conceptos", """
        CREATE TABLE IF NOT EXISTS cat_conceptos (
            id_concepto     INT AUTO_INCREMENT PRIMARY KEY,
            nombre_concepto VARCHAR(300),
            categoria       VARCHAR(200),
            orden_reporte   INT DEFAULT 99
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("cat_conceptos_unificados", """
        CREATE TABLE IF NOT EXISTS cat_conceptos_unificados (
            id_concepto        INT AUTO_INCREMENT PRIMARY KEY,
            nombre_concepto    VARCHAR(300),
            categoria          VARCHAR(200),
            orden_reporte      INT DEFAULT 99,
            codigo_cuenta_odoo VARCHAR(50)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("flujo_valores", """
        CREATE TABLE IF NOT EXISTS flujo_valores (
            id_valor         INT AUTO_INCREMENT PRIMARY KEY,
            id_concepto      INT,
            fecha_reporte    DATE,
            monto_proyectado DECIMAL(15,2) DEFAULT 0,
            monto_real       DECIMAL(15,2) DEFAULT 0,
            UNIQUE KEY uq_flujo (id_concepto, fecha_reporte),
            FOREIGN KEY (id_concepto) REFERENCES cat_conceptos(id_concepto) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("flujo_valores_unificados", """
        CREATE TABLE IF NOT EXISTS flujo_valores_unificados (
            id_valor         INT AUTO_INCREMENT PRIMARY KEY,
            id_concepto      INT,
            fecha_reporte    DATE,
            monto_proyectado DECIMAL(15,2) DEFAULT 0,
            monto_real       DECIMAL(15,2) DEFAULT 0,
            UNIQUE KEY uq_flujo_uni (id_concepto, fecha_reporte),
            FOREIGN KEY (id_concepto) REFERENCES cat_conceptos_unificados(id_concepto) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("gastos_operativos", """
        CREATE TABLE IF NOT EXISTS gastos_operativos (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            concepto        VARCHAR(300),
            categoria       VARCHAR(200),
            proveedor_fijo  VARCHAR(200),
            dia_pago_std    INT DEFAULT 1,
            monto_base      DECIMAL(15,2) DEFAULT 0,
            frecuencia      VARCHAR(20) DEFAULT 'MENSUAL',
            activo          TINYINT(1) DEFAULT 1,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("detalles_cuentas_odoo", """
        CREATE TABLE IF NOT EXISTS detalles_cuentas_odoo (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            id_concepto         INT,
            codigo_cuenta_odoo  VARCHAR(50),
            columna_saldo       VARCHAR(50),
            palabras_excluidas  TEXT,
            nomenclatura_ref    TEXT,
            palabras_incluidas  TEXT,
            FOREIGN KEY (id_concepto) REFERENCES cat_conceptos_unificados(id_concepto) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    # ── Multimarcas / clientes externos ──────────────────────────────────────
    ("clientes_multimarcas", """
        CREATE TABLE IF NOT EXISTS clientes_multimarcas (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            clave               VARCHAR(50),
            evac                VARCHAR(10),
            cliente_razon_social VARCHAR(300)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("multimarcas", """
        CREATE TABLE IF NOT EXISTS multimarcas (
            id                        INT AUTO_INCREMENT PRIMARY KEY,
            clave                     VARCHAR(50),
            evac                      VARCHAR(10),
            cliente_razon_social      VARCHAR(300),
            avance_global             DECIMAL(15,2) DEFAULT 0,
            avance_global_scott       DECIMAL(15,2) DEFAULT 0,
            avance_global_syncros     DECIMAL(15,2) DEFAULT 0,
            avance_global_apparel     DECIMAL(15,2) DEFAULT 0,
            avance_global_vittoria    DECIMAL(15,2) DEFAULT 0,
            avance_global_bold        DECIMAL(15,2) DEFAULT 0,
            total_facturas_julio      DECIMAL(15,2) DEFAULT 0,
            total_facturas_agosto     DECIMAL(15,2) DEFAULT 0,
            total_facturas_septiembre DECIMAL(15,2) DEFAULT 0,
            total_facturas_octubre    DECIMAL(15,2) DEFAULT 0,
            total_facturas_noviembre  DECIMAL(15,2) DEFAULT 0,
            total_facturas_diciembre  DECIMAL(15,2) DEFAULT 0,
            total_facturas_enero      DECIMAL(15,2) DEFAULT 0,
            total_facturas_febrero    DECIMAL(15,2) DEFAULT 0,
            total_facturas_marzo      DECIMAL(15,2) DEFAULT 0,
            total_facturas_abril      DECIMAL(15,2) DEFAULT 0,
            total_facturas_mayo       DECIMAL(15,2) DEFAULT 0,
            total_facturas_junio      DECIMAL(15,2) DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    # ── Retroactivos ──────────────────────────────────────────────────────────
    ("tabla_retroactivos", """
        CREATE TABLE IF NOT EXISTS tabla_retroactivos (
            id                           INT AUTO_INCREMENT PRIMARY KEY,
            id_previo                    INT,
            CLAVE                        VARCHAR(50),
            ZONA                         VARCHAR(10),
            CLIENTE                      VARCHAR(300),
            CATEGORIA                    VARCHAR(100),
            COMPRA_MINIMA_ANUAL          DECIMAL(15,2) DEFAULT 0,
            COMPRA_MINIMA_APPAREL        DECIMAL(15,2) DEFAULT 0,
            COMPRAS_TOTALES_CRUDO        DECIMAL(15,2) DEFAULT 0,
            META_MY26_CUMPLIDA           TINYINT(1) DEFAULT 0,
            COMPRA_GLOBAL_SCOTT          DECIMAL(15,2) DEFAULT 0,
            COMPRA_GLOBAL_APPAREL        DECIMAL(15,2) DEFAULT 0,
            COMPRA_GLOBAL_BOLD           DECIMAL(15,2) DEFAULT 0,
            TOTAL_ACUMULADO              DECIMAL(15,2) DEFAULT 0,
            compra_anual_crudo           DECIMAL(15,2) DEFAULT 0,
            compra_adicional             DECIMAL(15,2) DEFAULT 0,
            notas_credito                DECIMAL(15,2) DEFAULT 0,
            garantias                    DECIMAL(15,2) DEFAULT 0,
            productos_ofertados          DECIMAL(15,2) DEFAULT 0,
            bicicleta_demo               DECIMAL(15,2) DEFAULT 0,
            bicicletas_bold              DECIMAL(15,2) DEFAULT 0,
            importe_final                DECIMAL(15,2) DEFAULT 0,
            porcentaje_retroactivo       DECIMAL(8,6)  DEFAULT 0,
            porcentaje_retroactivo_apparel DECIMAL(8,6) DEFAULT 0,
            retroactivo_total            DECIMAL(8,6)  DEFAULT 0,
            importe                      DECIMAL(15,2) DEFAULT 0,
            estatus                      VARCHAR(50) DEFAULT 'Pendiente',
            fecha_aplicacion             DATE,
            NC                           TEXT,
            FACT                         TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    # ── Auditoría ─────────────────────────────────────────────────────────────
    ("auditoria_movimientos", """
        CREATE TABLE IF NOT EXISTS auditoria_movimientos (
            id                      INT AUTO_INCREMENT PRIMARY KEY,
            id_usuario              INT,
            nombre_usuario          VARCHAR(200),
            accion                  VARCHAR(100),
            tabla_afectada          VARCHAR(100),
            id_registro_afectado    INT,
            descripcion             TEXT,
            fecha_hora              DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_tabla (tabla_afectada),
            INDEX idx_fecha (fecha_hora)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    # ── Forecast / Proyecciones B2B ───────────────────────────────────────────
    ("odoo_catalogo", """
        CREATE TABLE IF NOT EXISTS odoo_catalogo (
            referencia_interna VARCHAR(255) PRIMARY KEY,
            nombre_producto    VARCHAR(255),
            categoria          VARCHAR(255),
            marca              VARCHAR(255),
            color              VARCHAR(255),
            talla              VARCHAR(255),
            actualizado_en     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("forecast_excel_productos", """
        CREATE TABLE IF NOT EXISTS forecast_excel_productos (
            sku            VARCHAR(255) PRIMARY KEY,
            nombre         VARCHAR(255),
            color          VARCHAR(255),
            talla          VARCHAR(255),
            origen         VARCHAR(50) DEFAULT 'excel',
            cargado_en     DATETIME DEFAULT CURRENT_TIMESTAMP,
            actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("forecast_sku_whitelist", """
        CREATE TABLE IF NOT EXISTS forecast_sku_whitelist (
            sku        VARCHAR(255) PRIMARY KEY,
            cargado_en DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),

    ("forecast_proyecciones", """
        CREATE TABLE IF NOT EXISTS forecast_proyecciones (
            id             INT AUTO_INCREMENT PRIMARY KEY,
            id_cliente     INT,
            clave_cliente  VARCHAR(255),
            periodo        VARCHAR(50),
            sku            VARCHAR(255),
            producto       VARCHAR(255),
            marca          VARCHAR(255),
            modelo         VARCHAR(255),
            color          VARCHAR(255),
            talla          VARCHAR(255),
            mayo           INT DEFAULT 0,
            junio          INT DEFAULT 0,
            julio          INT DEFAULT 0,
            agosto         INT DEFAULT 0,
            septiembre     INT DEFAULT 0,
            octubre        INT DEFAULT 0,
            noviembre      INT DEFAULT 0,
            diciembre      INT DEFAULT 0,
            enero          INT DEFAULT 0,
            febrero        INT DEFAULT 0,
            marzo          INT DEFAULT 0,
            abril          INT DEFAULT 0,
            creado_en      DATETIME DEFAULT CURRENT_TIMESTAMP,
            actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_forecast_clave_periodo_sku (clave_cliente, periodo, sku)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """),
]


def crear_tablas(conn):
    cur = conn.cursor()
    for nombre, sql in TABLAS:
        try:
            cur.execute(sql)
            print(f"  [OK] {nombre}")
        except Exception as e:
            print(f"  [ERROR] {nombre}: {e}")
    conn.commit()
    cur.close()


def insertar_datos_base(conn):
    cur = conn.cursor()

    # Roles
    cur.execute("INSERT IGNORE INTO roles (id, nombre) VALUES (1, 'Administrador'), (2, 'Usuario')")

    # Usuario admin
    hash_pw = bcrypt.hashpw(ADMIN_CONTRASENA.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cur.execute("""
        INSERT IGNORE INTO usuarios (usuario, contrasena, nombre, correo, rol_id, activo, flujo)
        VALUES (%s, %s, %s, %s, 1, 1, 1)
    """, (ADMIN_USUARIO, hash_pw, ADMIN_NOMBRE, ADMIN_CORREO))

    conn.commit()
    cur.close()
    print(f"\n[OK] Usuario admin creado -> usuario: '{ADMIN_USUARIO}'  contraseña: '{ADMIN_CONTRASENA}'")


def main():
    print(f"\n{'='*55}")
    print(f"  Setup BD local: {USER}@{HOST}:{PORT} -> {DATABASE}")
    print(f"{'='*55}\n")

    try:
        # 1. Conectar sin seleccionar DB para crearla
        conn_root = conectar()
        crear_base_de_datos(conn_root)
        conn_root.close()

        # 2. Conectar con la BD ya creada
        conn = conectar(database=DATABASE)
        print("\nCreando tablas:")
        crear_tablas(conn)

        print("\nInsertando datos base:")
        insertar_datos_base(conn)

        conn.close()
        print(f"\n{'='*55}")
        print("  [OK] Setup completado exitosamente.")
        print(f"{'='*55}\n")

    except mysql.connector.Error as e:
        print(f"\n[ERROR] Error de conexión MySQL: {e}")
        print(f"   Verifica que MySQL esté corriendo en {HOST}:{PORT}")
        print(f"   y que las credenciales {USER}/{PASSWORD} sean correctas.\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
