"""Capa de acceso a datos (Data Access) para Solicitud de Retroactivos.

Cada función recibe un cursor ya abierto (dictionary=True, buffered=True,
mismo cursor que routes/solicitud_retroactivo.py ya creaba) y ejecuta
exactamente el mismo SQL/stored procedure que antes vivía inline en la
ruta. No valida, no calcula montos, no decide respuestas HTTP ni hace
commit/rollback -- esa lógica de negocio y el manejo de la conexión se
quedan en las rutas, sin cambios.
"""

# GUÍA: MY27 corre del 1-jul-2026 al 30-jun-2027; MY28 el mismo rango un año
# después, etc. No es un campo capturado -- se deriva de fecha_venta.
ANIO_MODELO_SQL = """
    CASE
        WHEN MONTH(v.fecha_venta) >= 7 THEN CONCAT('MY', LPAD((YEAR(v.fecha_venta) + 1) % 100, 2, '0'))
        ELSE CONCAT('MY', LPAD(YEAR(v.fecha_venta) % 100, 2, '0'))
    END
"""


def obtener_porcentaje_msi(cursor, id_msi):
    cursor.execute("SELECT fn_ObtenerPorcentajeMsi(%s) AS porcentaje;", (id_msi,))
    return cursor.fetchone()


def crear_venta(cursor, parametros):
    cursor.callproc('sp_solicitud_retroactivo_crear_venta', parametros)
    while cursor.nextset():
        pass


def obtener_id_por_numero_serie(cursor, numero_serie):
    cursor.execute(
        "SELECT id FROM solicitud_retroactivo_venta WHERE numero_serie = %s",
        (numero_serie,)
    )
    return cursor.fetchone()


def guardar_historial_inicial(cursor, id_venta, historial_json):
    cursor.execute(
        "UPDATE solicitud_retroactivo_venta SET historial_json = %s WHERE id = %s",
        (historial_json, id_venta)
    )


def buscar_msi(cursor):
    cursor.callproc('sp_solicitud_retroactivo_buscar_msi')
    datos = []
    for resultado in cursor.stored_results():
        datos = resultado.fetchall()
    while cursor.nextset():
        pass
    return datos


def buscar_marca(cursor):
    cursor.callproc('sp_solicitud_retroactivo_buscar_marca')
    datos = []
    for resultado in cursor.stored_results():
        datos = resultado.fetchall()
    while cursor.nextset():
        pass
    return datos


def buscar_formulario(cursor):
    cursor.callproc('sp_solicitud_retroactivo_buscar_formulario')
    datos = []
    for resultado in cursor.stored_results():
        datos = resultado.fetchall()
    while cursor.nextset():
        pass
    return datos


def buscar_razones_sociales(cursor):
    cursor.execute("""
        SELECT DISTINCT c.id, c.nombre_cliente, c.clave
        FROM clientes c
        INNER JOIN usuarios u ON u.cliente_id = c.id
        WHERE u.rol_id = 2
          AND c.nombre_cliente IS NOT NULL
          AND c.nombre_cliente != ''
        ORDER BY c.nombre_cliente ASC
    """)
    datos = cursor.fetchall()
    if not datos:
        cursor.execute("""
            SELECT DISTINCT c.id, c.nombre_cliente, c.clave
            FROM clientes c
            INNER JOIN usuarios u ON u.cliente_id = c.id
            WHERE u.rol_id = 2
            ORDER BY c.nombre_cliente ASC
        """)
        datos = cursor.fetchall()
    return datos


def asegurar_tabla_tiendas(cursor):
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tiendas (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nombre VARCHAR(255) NOT NULL,
                cliente_id INT NOT NULL,
                KEY idx_cliente (cliente_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
    except Exception:
        pass


def buscar_tiendas_por_cliente(cursor, cliente_id):
    asegurar_tabla_tiendas(cursor)
    cursor.execute("""
        SELECT id, nombre, cliente_id
        FROM tiendas
        WHERE cliente_id = %s
        ORDER BY nombre ASC
    """, (cliente_id,))
    return cursor.fetchall()


def obtener_nombres_cliente_y_tienda(cursor, cliente_id, tienda_id):
    nombre_cliente = None
    nombre_sucursal = None

    if cliente_id:
        cursor.execute("SELECT nombre_cliente FROM clientes WHERE id = %s", (cliente_id,))
        res_c = cursor.fetchone()
        if res_c:
            nombre_cliente = res_c.get('nombre_cliente')

    if tienda_id:
        asegurar_tabla_tiendas(cursor)
        cursor.execute("SELECT nombre FROM tiendas WHERE id = %s", (tienda_id,))
        res_t = cursor.fetchone()
        if res_t:
            nombre_sucursal = res_t.get('nombre')

    return nombre_cliente, nombre_sucursal


def listar_ventas(cursor):
    cursor.execute(f"""
        SELECT
            v.id, v.id_usuario, v.id_formulario, f.nombre AS nombre_formulario,
            v.id_marca_bicicleta, v.id_msi, m.plazo_meses,
            v.nombre_sucursal, v.correo_electronico, v.nombre_completo,
            v.fecha_venta, v.modelo_bicicleta, v.numero_serie,
            v.precio_publico, v.porcentaje, v.monto_pagar, v.monto_aplicar, v.nota_credito,
            v.validacion_docs_json, v.historial_json, {ANIO_MODELO_SQL} AS anio_modelo,
            v.ticket_compra_key, v.voucher_key, v.factura_pdf_key, v.factura_xml_key,
            v.fecha_registro
        FROM solicitud_retroactivo_venta v
        LEFT JOIN solicitud_retroactivo_formulario f ON f.id = v.id_formulario
        LEFT JOIN solicitud_retroactivo_msi m ON m.id = v.id_msi
        ORDER BY v.fecha_registro DESC
    """)
    return cursor.fetchall()


def obtener_totales_generales(cursor):
    cursor.execute("""
        SELECT
            COUNT(*) AS total_solicitudes,
            COALESCE(SUM(monto_pagar), 0) AS monto_total_pagar,
            COALESCE(SUM(monto_aplicar), 0) AS monto_total_aplicar
        FROM solicitud_retroactivo_venta
    """)
    return cursor.fetchone()


def obtener_validaciones_docs(cursor):
    cursor.execute("SELECT validacion_docs_json FROM solicitud_retroactivo_venta")
    return cursor.fetchall()


def obtener_dashboard_por_campana(cursor):
    cursor.execute("""
        SELECT
            v.id_formulario, COALESCE(f.nombre, 'Sin campaña') AS nombre_formulario,
            COUNT(*) AS total_solicitudes, COALESCE(SUM(v.monto_pagar), 0) AS monto_total
        FROM solicitud_retroactivo_venta v
        LEFT JOIN solicitud_retroactivo_formulario f ON f.id = v.id_formulario
        GROUP BY v.id_formulario, f.nombre
        ORDER BY monto_total DESC
    """)
    return cursor.fetchall()


def obtener_dashboard_por_cliente(cursor):
    cursor.execute("""
        SELECT
            nombre_completo, correo_electronico,
            COUNT(*) AS total_solicitudes, COALESCE(SUM(monto_pagar), 0) AS monto_total
        FROM solicitud_retroactivo_venta
        GROUP BY nombre_completo, correo_electronico
        ORDER BY monto_total DESC
    """)
    return cursor.fetchall()


def obtener_dashboard_por_anio_modelo(cursor):
    cursor.execute(f"""
        SELECT
            {ANIO_MODELO_SQL} AS anio_modelo,
            COUNT(*) AS total_solicitudes, COALESCE(SUM(v.monto_pagar), 0) AS monto_total
        FROM solicitud_retroactivo_venta v
        GROUP BY anio_modelo
        ORDER BY anio_modelo DESC
    """)
    return cursor.fetchall()


def obtener_dashboard_por_producto(cursor):
    cursor.execute("""
        SELECT
            COALESCE(TRIM(modelo_bicicleta), 'Sin producto') AS producto,
            COUNT(*) AS total_solicitudes,
            COALESCE(SUM(monto_pagar), 0) AS monto_total_pagar,
            COALESCE(SUM(monto_aplicar), 0) AS monto_total_aplicar
        FROM solicitud_retroactivo_venta
        GROUP BY COALESCE(TRIM(modelo_bicicleta), 'Sin producto')
        ORDER BY monto_total_pagar DESC
    """)
    return cursor.fetchall()


def obtener_venta_para_validacion(cursor, id_venta):
    cursor.execute(
        "SELECT validacion_docs_json, historial_json FROM solicitud_retroactivo_venta WHERE id = %s",
        (id_venta,)
    )
    return cursor.fetchone()


def actualizar_validacion_documento(cursor, id_venta, validacion_docs_json, historial_json):
    cursor.execute(
        "UPDATE solicitud_retroactivo_venta SET validacion_docs_json = %s, historial_json = %s WHERE id = %s",
        (validacion_docs_json, historial_json, id_venta)
    )


def obtener_venta_para_nota_credito(cursor, id_venta):
    cursor.execute(
        "SELECT nota_credito, historial_json FROM solicitud_retroactivo_venta WHERE id = %s",
        (id_venta,)
    )
    return cursor.fetchone()


def actualizar_nota_credito(cursor, id_venta, nota_credito, historial_json):
    cursor.execute(
        "UPDATE solicitud_retroactivo_venta SET nota_credito = %s, historial_json = %s WHERE id = %s",
        (nota_credito, historial_json, id_venta)
    )


def obtener_venta_para_precio(cursor, id_venta):
    cursor.execute(
        "SELECT porcentaje, precio_publico, historial_json FROM solicitud_retroactivo_venta WHERE id = %s",
        (id_venta,)
    )
    return cursor.fetchone()


def actualizar_precio(cursor, id_venta, precio_publico, monto_pagar, monto_aplicar, historial_json):
    cursor.execute(
        "UPDATE solicitud_retroactivo_venta SET precio_publico = %s, monto_pagar = %s, monto_aplicar = %s, historial_json = %s WHERE id = %s",
        (precio_publico, monto_pagar, monto_aplicar, historial_json, id_venta)
    )


def listar_mis_ventas(cursor, id_usuario):
    cursor.execute(f"""
        SELECT
            v.id, v.id_formulario, f.nombre AS nombre_formulario,
            v.id_marca_bicicleta, v.id_msi, m.plazo_meses,
            v.nombre_sucursal, v.correo_electronico, v.nombre_completo,
            v.fecha_venta, v.modelo_bicicleta, v.numero_serie,
            v.precio_publico, v.porcentaje, v.monto_pagar, v.nota_credito,
            v.validacion_docs_json, v.historial_json, {ANIO_MODELO_SQL} AS anio_modelo,
            v.ticket_compra_key, v.voucher_key, v.factura_pdf_key, v.factura_xml_key,
            v.fecha_registro
        FROM solicitud_retroactivo_venta v
        LEFT JOIN solicitud_retroactivo_formulario f ON f.id = v.id_formulario
        LEFT JOIN solicitud_retroactivo_msi m ON m.id = v.id_msi
        WHERE v.id_usuario = %s
        ORDER BY v.fecha_registro DESC
    """, (id_usuario,))
    return cursor.fetchall()


def obtener_venta_para_edicion(cursor, id_venta):
    cursor.execute(
        "SELECT id_usuario, validacion_docs_json, historial_json FROM solicitud_retroactivo_venta WHERE id = %s",
        (id_venta,)
    )
    return cursor.fetchone()


def actualizar_venta(cursor, id_venta, valores_fijos, columnas_archivo_sql, valores_archivo):
    """valores_fijos: tupla en el mismo orden que las columnas fijas del SET
    (id_formulario, id_marca_bicicleta, id_msi, nombre_sucursal,
    correo_electronico, nombre_completo, fecha_venta, modelo_bicicleta,
    numero_serie, precio_publico, porcentaje, monto_pagar, monto_aplicar,
    validacion_docs_json, historial_json). columnas_archivo_sql: string tipo
    "ticket_compra_key = %s, voucher_key = %s" (o '' si no hay archivos que
    resubir). valores_archivo: valores para esas columnas, en el mismo orden.
    """
    set_archivos = f", {columnas_archivo_sql}" if columnas_archivo_sql else ""
    cursor.execute(f"""
        UPDATE solicitud_retroactivo_venta SET
            id_formulario = %s, id_marca_bicicleta = %s, id_msi = %s,
            nombre_sucursal = %s, correo_electronico = %s, nombre_completo = %s,
            fecha_venta = %s, modelo_bicicleta = %s, numero_serie = %s,
            precio_publico = %s, porcentaje = %s, monto_pagar = %s, monto_aplicar = %s,
            validacion_docs_json = %s, historial_json = %s
            {set_archivos}
        WHERE id = %s
    """, (*valores_fijos, *valores_archivo, id_venta))