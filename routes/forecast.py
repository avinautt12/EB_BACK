"""
Forecast / Proyecciones B2B
Gestión del forecast anual de compra por distribuidor.
Periodo comercial: Mayo–Abril (e.g., "2026-2027")
"""
from flask import Blueprint, jsonify, request, send_file
from db_conexion import obtener_conexion
from services.forecast_excel_service import (
    load_excel_products,
    list_excel_products,
    delete_excel_product,
    clear_excel_catalog,
    get_valid_skus
)
import io
import re
import threading
import logging
from datetime import datetime

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False

forecast_bp = Blueprint('forecast', __name__, url_prefix='')

# ── Caché en memoria para el cruce Odoo (TTL = 3 minutos) ────────────────────
# Evita repetir las llamadas XML-RPC lentas cuando el usuario recarga la vista
# o cambia de pestaña dentro del mismo periodo.
import time as _time
_avance_cache: dict = {}   # key: (clave, periodo) → (timestamp, result_list)
_AVANCE_TTL = 180          # segundos

# Orden de meses en el periodo comercial Mayo–Abril
MESES = ['mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
         'noviembre', 'diciembre', 'enero', 'febrero', 'marzo', 'abril']
MESES_LABELS = ['May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic', 'Ene', 'Feb', 'Mar', 'Abr']

CAMPOS_INFO = ['SKU', 'Producto', 'Marca', 'Modelo', 'Color', 'Talla']

# ─────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────

def _ensure_table():
    """Create forecast_proyecciones if it doesn't exist (idempotent)."""
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS forecast_proyecciones (
            id INT PRIMARY KEY AUTO_INCREMENT,
            id_cliente INT NOT NULL,
            clave_cliente VARCHAR(20) NOT NULL,
            periodo VARCHAR(9) NOT NULL,
            sku VARCHAR(100) NOT NULL,
            producto VARCHAR(255) NOT NULL,
            marca VARCHAR(100) DEFAULT NULL,
            modelo VARCHAR(100) DEFAULT NULL,
            color VARCHAR(100) DEFAULT NULL,
            talla VARCHAR(50) DEFAULT NULL,
            mayo INT NOT NULL DEFAULT 0,
            junio INT NOT NULL DEFAULT 0,
            julio INT NOT NULL DEFAULT 0,
            agosto INT NOT NULL DEFAULT 0,
            septiembre INT NOT NULL DEFAULT 0,
            octubre INT NOT NULL DEFAULT 0,
            noviembre INT NOT NULL DEFAULT 0,
            diciembre INT NOT NULL DEFAULT 0,
            enero INT NOT NULL DEFAULT 0,
            febrero INT NOT NULL DEFAULT 0,
            marzo INT NOT NULL DEFAULT 0,
            abril INT NOT NULL DEFAULT 0,
            creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            actualizado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_forecast (clave_cliente, periodo, sku),
            INDEX idx_cliente_periodo (clave_cliente, periodo),
            FOREIGN KEY (id_cliente) REFERENCES clientes(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    conn.commit()
    cur.close()
    conn.close()

_ensure_table()


# ─────────────────────────────────────────────────────
# Odoo catalog sync (odoo_catalogo table)
# ─────────────────────────────────────────────────────

def _ensure_catalogo_table():
    """Create odoo_catalogo table if it doesn't exist."""
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS odoo_catalogo (
            referencia_interna VARCHAR(150) NOT NULL,
            nombre_producto    VARCHAR(400) NOT NULL,
            categoria          VARCHAR(600) DEFAULT NULL,
            marca              VARCHAR(150) DEFAULT NULL,
            color              VARCHAR(150) DEFAULT NULL,
            talla              VARCHAR(100) DEFAULT NULL,
            actualizado_en     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP
                               ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (referencia_interna),
            FULLTEXT idx_ft_nombre (nombre_producto),
            INDEX idx_marca (marca)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
    """)
    # Add columns if they don't exist yet (for existing installations)
    for col_def in [
        "ALTER TABLE odoo_catalogo ADD COLUMN IF NOT EXISTS color VARCHAR(150) DEFAULT NULL",
        "ALTER TABLE odoo_catalogo ADD COLUMN IF NOT EXISTS talla VARCHAR(100) DEFAULT NULL",
    ]:
        try:
            cur.execute(col_def)
        except Exception:
            pass
    conn.commit()
    cur.close()
    conn.close()


_ensure_catalogo_table()
_catalogo_sync_lock = threading.Lock()
_catalogo_syncing   = False


# ─────────────────────────────────────────────────────
# Excel Product Catalog (forecast_excel_productos table)
# ─────────────────────────────────────────────────────
# Allows loading products from Excel before they exist in Odoo
# Used as validation source for product SKUs in forecasts

def _ensure_excel_producto_table():
    """Create forecast_excel_productos table if it doesn't exist."""
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS forecast_excel_productos (
            sku VARCHAR(100) NOT NULL PRIMARY KEY,
            nombre VARCHAR(400) NOT NULL,
            color VARCHAR(150) DEFAULT NULL,
            talla VARCHAR(100) DEFAULT NULL,
            origen ENUM('excel', 'odoo') DEFAULT 'excel',
            cargado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            actualizado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_origen (origen),
            FULLTEXT idx_ft_nombre (nombre)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    conn.commit()
    cur.close()
    conn.close()


_ensure_excel_producto_table()


def _get_product_from_sources(sku: str) -> dict or None:
    """
    Busca un producto por SKU en ambas fuentes (Excel primero, luego Odoo).
    Retorna dict con keys: sku, nombre, color, talla, origen
    o None si no existe en ninguna fuente.
    """
    conn = obtener_conexion()
    cur = conn.cursor(dictionary=True)
    try:
        # Buscar primero en Excel (tiene prioridad)
        cur.execute("""
            SELECT sku, nombre, color, talla, origen
            FROM forecast_excel_productos
            WHERE sku = %s AND origen = 'excel'
        """, (sku,))
        row = cur.fetchone()
        if row:
            return row

        # Fallback a Odoo catalog
        cur.execute("""
            SELECT referencia_interna AS sku, 
                   nombre_producto AS nombre,
                   color,
                   talla,
                   'odoo' AS origen
            FROM odoo_catalogo
            WHERE referencia_interna = %s
        """, (sku,))
        row = cur.fetchone()
        if row:
            return row

        return None
    finally:
        cur.close()
        conn.close()


def _sync_catalogo_odoo_task():
    """Fetch all active product variants from Odoo and upsert into odoo_catalogo."""
    global _catalogo_syncing
    try:
        from utils.odoo_utils import get_odoo_models, ODOO_DB, ODOO_PASSWORD
        uid, models, err = get_odoo_models()
        if not uid:
            logging.warning('[catalogo_sync] Could not connect to Odoo: %s', err)
            return

        batch_size = 500
        offset     = 0
        total_upserted = 0
        conn = obtener_conexion()
        cur  = conn.cursor()

        while True:
            records = models.execute_kw(
                ODOO_DB, uid, ODOO_PASSWORD,
                'product.product', 'search_read',
                [[['active', '=', True]]],
                {'fields': ['id', 'default_code', 'name', 'categ_id',
                            'product_template_attribute_value_ids'],
                 'limit': batch_size, 'offset': offset,
                 'order': 'id asc'}
            )
            if not records:
                break

            # Batch-fetch variant attribute values (color, talla) for all products in this page
            all_ptav_ids = []
            for p in records:
                all_ptav_ids.extend(p.get('product_template_attribute_value_ids') or [])
            ptav_map = {}  # ptav_id → {'attr': str, 'val': str}
            if all_ptav_ids:
                ptav_recs = models.execute_kw(
                    ODOO_DB, uid, ODOO_PASSWORD,
                    'product.template.attribute.value', 'read',
                    [all_ptav_ids],
                    {'fields': ['id', 'attribute_id', 'name']}
                )
                for pv in ptav_recs:
                    attr_name = ((pv.get('attribute_id') or [None, ''])[1] or '').upper()
                    ptav_map[pv['id']] = {
                        'attr': attr_name,
                        'val':  (pv.get('name') or '').upper().strip()
                    }

            rows = []
            for p in records:
                ref  = (p.get('default_code') or '').strip()
                if not ref:
                    ref = f'ODOO:{p["id"]}'  # synthetic SKU for products without referencia_interna
                nombre   = (p.get('name') or '').upper().strip()
                categ    = p.get('categ_id', [None, ''])
                categoria = (categ[1] if categ and len(categ) > 1 else '').strip()
                # First segment of the category path is the brand
                marca = categoria.split(' / ')[0].strip() if categoria else ''
                # Extract color and talla from Odoo variant attributes
                color = ''
                talla = ''
                for ptav_id in (p.get('product_template_attribute_value_ids') or []):
                    pv = ptav_map.get(ptav_id)
                    if not pv:
                        continue
                    if any(k in pv['attr'] for k in ('COLOR', 'COLO', 'COLOUR')):
                        color = pv['val']
                    elif any(k in pv['attr'] for k in ('TALLA', 'TAMAÑO', 'SIZE', 'TAMA')):
                        talla = pv['val']
                rows.append((ref, nombre, categoria, marca, color, talla))

            if rows:
                cur.executemany(
                    """
                    INSERT INTO odoo_catalogo
                        (referencia_interna, nombre_producto, categoria, marca, color, talla)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        nombre_producto = VALUES(nombre_producto),
                        categoria       = VALUES(categoria),
                        marca           = VALUES(marca),
                        color           = VALUES(color),
                        talla           = VALUES(talla),
                        actualizado_en  = NOW()
                    """,
                    rows
                )
                conn.commit()
                total_upserted += len(rows)

            if len(records) < batch_size:
                break
            offset += batch_size

        cur.close()
        conn.close()
        logging.info('[catalogo_sync] Done — %d products upserted.', total_upserted)
    except Exception as exc:
        logging.exception('[catalogo_sync] Error: %s', exc)
    finally:
        with _catalogo_sync_lock:
            _catalogo_syncing = False


def _trigger_catalogo_sync(force: bool = False):
    """Launch a background sync if not already running (and table is empty or force=True)."""
    global _catalogo_syncing
    with _catalogo_sync_lock:
        if _catalogo_syncing:
            return 'already_running'
        if not force:
            conn = obtener_conexion()
            cur  = conn.cursor()
            cur.execute('SELECT COUNT(*) as cnt FROM odoo_catalogo')
            cnt = cur.fetchone()[0]
            cur.close()
            conn.close()
            if cnt > 0:
                return 'already_populated'
        _catalogo_syncing = True

    t = threading.Thread(target=_sync_catalogo_odoo_task, daemon=True, name='catalogo_sync')
    t.start()
    return 'started'


# Auto-sync on startup if the catalog is empty
_trigger_catalogo_sync(force=False)


SIZE_RE = re.compile(r'^(XS|S|M|L|XL|XXL|XXXL|TU|\d{1,3})$', re.IGNORECASE)
CATEGORY_PREFIXES = [
    'BICICLETA', 'BICI', 'CASCO', 'GUANTE', 'GUANTES', 'LENTE', 'LENTES', 'BOLSO',
    'MOCHILA', 'ZAPATILLA', 'ZAPATILLAS', 'ZAPATO', 'ZAPATOS', 'JERSEY',
    'SHORTS', 'CHAMARRA', 'GORRA', 'GAFAS', 'ACCESORIO', 'ACCESORIOS',
    'ROPA', 'MANUBRIO', 'SILLA', 'SILLÍN', 'RUEDA',
]

def _parse_color_talla(descripcion: str, modelo: str) -> tuple:
    """Heuristically extract (color, talla) from a product descripcion string."""
    if not descripcion:
        return '', ''
    text = descripcion.upper().strip()
    modelo_up = modelo.upper().strip() if modelo else ''
    # Strip year suffix like MY26, MY2026 from modelo before matching
    modelo_base = re.sub(r'\s+MY\d{2,4}$', '', modelo_up).strip()
    # Try to remove modelo (with or without year suffix)
    for m in [modelo_up, modelo_base]:
        if m and m in text:
            text = text.replace(m, '').strip()
            break
    # Remove category prefix
    for prefix in CATEGORY_PREFIXES:
        if text.startswith(prefix + ' ') or text == prefix:
            text = text[len(prefix):].strip()
            break
    tokens = text.split()
    if not tokens:
        return '', ''
    last = tokens[-1]
    if SIZE_RE.match(last):
        talla = last
        color = ' '.join(tokens[:-1]).strip()
    else:
        talla = ''
        color = ' '.join(tokens).strip()
    return color, talla


def _clean_producto(descripcion: str, color: str, talla: str) -> str:
    """Remove color/talla tokens from the end of a product description."""
    name = descripcion.strip()
    if talla:
        name = re.sub(r'\s+' + re.escape(talla) + r'\s*$', '', name, flags=re.IGNORECASE).strip()
    if color:
        name = re.sub(r'\s+' + re.escape(color) + r'\s*$', '', name, flags=re.IGNORECASE).strip()
    return name


def _get_client_id(clave_cliente: str) -> int | None:
    conn = obtener_conexion()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT id FROM clientes WHERE clave = %s LIMIT 1", (clave_cliente,))
        row = cur.fetchone()
        return row['id'] if row else None
    finally:
        cur.close()
        conn.close()


def _get_authorized_products(clave_cliente: str, id_cliente: int) -> list:
    """
    Returns list of dicts with keys: sku, producto, marca, modelo, color, talla.
    Uses proyecciones_cliente → proyecciones_ventas as primary source.
    Falls back to full proyecciones_ventas catalog if no rows found.
    """
    conn = obtener_conexion()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT DISTINCT
                pv.clave_factura              AS sku,
                pv.descripcion               AS producto,
                pv.modelo                    AS modelo,
                pv.spec                      AS spec,
                COALESCE(oc.marca, m.marca, '') AS marca
            FROM proyecciones_ventas pv
            JOIN proyecciones_cliente pc ON pc.id_proyeccion = pv.id
            LEFT JOIN odoo_catalogo oc ON oc.referencia_interna = pv.clave_odoo
            LEFT JOIN (
                SELECT referencia_interna, MAX(marca) AS marca
                FROM monitor
                WHERE marca IS NOT NULL AND marca != ''
                GROUP BY referencia_interna
            ) m ON m.referencia_interna = pv.clave_factura
            WHERE pc.id_cliente = %s
            ORDER BY pv.clave_factura
        """, (id_cliente,))
        rows = cur.fetchall()

        if not rows:
            cur.execute("""
                SELECT DISTINCT
                    pv.clave_factura              AS sku,
                    pv.descripcion               AS producto,
                    pv.modelo                    AS modelo,
                    pv.spec                      AS spec,
                    COALESCE(oc.marca, m.marca, '') AS marca
                FROM proyecciones_ventas pv
                LEFT JOIN odoo_catalogo oc ON oc.referencia_interna = pv.clave_odoo
                LEFT JOIN (
                    SELECT referencia_interna, MAX(marca) AS marca
                    FROM monitor
                    WHERE marca IS NOT NULL AND marca != ''
                    GROUP BY referencia_interna
                ) m ON m.referencia_interna = pv.clave_factura
                ORDER BY pv.clave_factura
            """)
            rows = cur.fetchall()

        result = []
        for r in rows:
            color, talla = _parse_color_talla(r['producto'] or '', r['modelo'] or '')
            result.append({
                'sku':      r['sku'] or '',
                'producto': _clean_producto(r['producto'] or '', color, talla),
                'marca':    r['marca'] or '',
                'modelo':   r['modelo'] or '',
                'color':    color,
                'talla':    talla,
            })
        return result
    finally:
        cur.close()
        conn.close()


def _validate_periodo(periodo: str) -> bool:
    """Validates format YYYY-YYYY with second year = first + 1."""
    m = re.match(r'^(\d{4})-(\d{4})$', periodo or '')
    if not m:
        return False
    a1, a2 = int(m.group(1)), int(m.group(2))
    return a2 == a1 + 1


# ─────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────

@forecast_bp.route('/forecast/template', methods=['GET'])
def descargar_template():
    """
    GET /forecast/template?clave=<clave_cliente>&periodo=<periodo>
    Returns an xlsx file pre-filled with the client's authorized products
    and empty monthly columns (May–Abr).
    """
    if not OPENPYXL_OK:
        return jsonify({'error': 'openpyxl no instalado en el servidor'}), 500

    clave = request.args.get('clave', '').strip()
    periodo = request.args.get('periodo', '').strip()

    if not clave:
        return jsonify({'error': 'Falta parámetro clave'}), 400
    if not _validate_periodo(periodo):
        return jsonify({'error': 'Formato de periodo inválido (use YYYY-YYYY)'}), 400

    id_cliente = _get_client_id(clave)
    if id_cliente is None:
        return jsonify({'error': f'Cliente "{clave}" no encontrado'}), 404

    products = _get_authorized_products(clave, id_cliente)

    # Pick 5 diverse example rows: one per distinct marca, then one per modelo
    seen_marcas: set = set()
    sample: list = []
    for p in products:
        key = (p.get('marca') or '').upper() or p.get('modelo', '')
        if key not in seen_marcas:
            seen_marcas.add(key)
            sample.append(p)
        if len(sample) == 5:
            break
    # Fill remaining slots from different modelos if fewer than 5 marcas
    if len(sample) < 5:
        seen_modelos = {p.get('modelo', '') for p in sample}
        for p in products:
            if p not in sample and p.get('modelo', '') not in seen_modelos:
                seen_modelos.add(p.get('modelo', ''))
                sample.append(p)
            if len(sample) == 5:
                break
    products = sample

    # ── Build Excel ──
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f'Forecast {periodo}'

    ORANGE = 'FFEB5E28'
    DARK_BG = 'FF252422'
    HEADER_BG = 'FF1A1918'
    LIGHT_GREY = 'FFD0D0D0'
    EDITABLE_BG = 'FFFEFEFE'

    header_font  = Font(bold=True, color='FFFFFFFF', size=10)
    info_font    = Font(bold=True, color='FFFFFFFF', size=10)
    locked_font  = Font(color='FF888888', size=9)
    editable_font= Font(color='FF111111', size=10)
    month_header = Font(bold=True, color='FFFFFFFF', size=10)

    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    left   = Alignment(horizontal='left',   vertical='center', wrap_text=True)

    thin = Side(style='thin', color='FF666666')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # Row 1 – Title
    ws.merge_cells('A1:R1')
    title_cell = ws['A1']
    title_cell.value = f'Forecast de Compra — Periodo Comercial {periodo}   |   Distribuidor: {clave}'
    title_cell.font = Font(bold=True, color='FFEB5E28', size=12)
    title_cell.fill = PatternFill('solid', fgColor=HEADER_BG)
    title_cell.alignment = center
    ws.row_dimensions[1].height = 28

    # Row 2 – Column headers
    HEADERS = CAMPOS_INFO + MESES_LABELS + ['TOTAL']
    for col_idx, h in enumerate(HEADERS, start=1):
        cell = ws.cell(row=2, column=col_idx, value=h)
        if h in CAMPOS_INFO:
            cell.fill = PatternFill('solid', fgColor=DARK_BG)
            cell.font = info_font
        elif h == 'TOTAL':
            cell.fill = PatternFill('solid', fgColor=ORANGE)
            cell.font = Font(bold=True, color='FF000000', size=10)
        else:
            cell.fill = PatternFill('solid', fgColor=ORANGE)
            cell.font = month_header
        cell.alignment = center
        cell.border = border
    ws.row_dimensions[2].height = 22

    # Row 3 – Instructions note
    ws.merge_cells('A3:R3')
    note = ws['A3']
    note.value = (
        'INSTRUCCIONES: Complete las cantidades de los productos precargados y/o agregue filas con nuevos productos. '
        'Para nuevos productos ingrese SKU (del catálogo autorizado), Producto, Marca, Modelo, Color y Talla. '
        'Las cantidades deben ser números enteros ≥ 0. '
        'Guarde y cargue este archivo en el sistema.'
    )
    note.font = Font(italic=True, color='FF444444', size=9)
    note.fill = PatternFill('solid', fgColor='FFFFF8F0')
    note.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
    ws.row_dimensions[3].height = 30

    # Data rows
    total_col = len(HEADERS)  # column index of TOTAL
    for row_idx, p in enumerate(products, start=4):
        info_values = [
            p['sku'], p['producto'], p['marca'], p['modelo'], p['color'], p['talla']
        ]
        for ci, val in enumerate(info_values, start=1):
            c = ws.cell(row=row_idx, column=ci, value=val)
            c.font = editable_font
            c.fill = PatternFill('solid', fgColor='FFFAFAFA')
            c.alignment = left if ci == 2 else center
            c.border = border

        # Month columns
        month_start_col = len(CAMPOS_INFO) + 1
        for mi in range(len(MESES)):
            c = ws.cell(row=row_idx, column=month_start_col + mi, value=0)
            c.font = editable_font
            c.fill = PatternFill('solid', fgColor=EDITABLE_BG)
            c.alignment = center
            c.border = border
            c.number_format = '0'
            c.protection = openpyxl.styles.Protection(locked=False)

        # TOTAL formula
        first_m = get_column_letter(month_start_col)
        last_m  = get_column_letter(month_start_col + len(MESES) - 1)
        tc = ws.cell(row=row_idx, column=total_col)
        tc.value = f'=SUM({first_m}{row_idx}:{last_m}{row_idx})'
        tc.font = Font(bold=True, color='FF000000', size=10)
        tc.fill = PatternFill('solid', fgColor='FFFFF0D0')
        tc.alignment = center
        tc.border = border
        tc.number_format = '0'

    # Blank editable rows for clients to add new products
    blank_start = 4 + len(products)
    month_start_col = len(CAMPOS_INFO) + 1
    for blank_offset in range(15):
        row_idx = blank_start + blank_offset
        for ci in range(1, len(CAMPOS_INFO) + 1):
            c = ws.cell(row=row_idx, column=ci)
            c.fill = PatternFill('solid', fgColor='FFFAFAFA')
            c.alignment = left if ci == 2 else center
            c.border = border
        for mi in range(len(MESES)):
            c = ws.cell(row=row_idx, column=month_start_col + mi)
            c.fill = PatternFill('solid', fgColor=EDITABLE_BG)
            c.alignment = center
            c.border = border
            c.number_format = '0'
        first_m = get_column_letter(month_start_col)
        last_m  = get_column_letter(month_start_col + len(MESES) - 1)
        tc = ws.cell(row=row_idx, column=total_col)
        tc.value = f'=SUM({first_m}{row_idx}:{last_m}{row_idx})'
        tc.font = Font(bold=True, color='FF000000', size=10)
        tc.fill = PatternFill('solid', fgColor='FFFFF0D0')
        tc.alignment = center
        tc.border = border
        tc.number_format = '0'

    # Widths
    col_widths = [18, 42, 16, 22, 14, 8] + [7]*12 + [9]
    for ci, w in enumerate(col_widths, start=1):
        ws.column_dimensions[get_column_letter(ci)].width = w

    # Freeze header rows
    ws.freeze_panes = 'A4'

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f'Forecast_{clave}_{periodo}.xlsx'
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@forecast_bp.route('/forecast/importar', methods=['POST'])
def importar_forecast():
    """
    POST /forecast/importar  (multipart/form-data)
    Fields: clave_cliente, periodo, file (xlsx)
    Validates and upserts rows into forecast_proyecciones.
    """
    if not OPENPYXL_OK:
        return jsonify({'error': 'openpyxl no instalado en el servidor'}), 500

    clave  = request.form.get('clave_cliente', '').strip()
    periodo = request.form.get('periodo', '').strip()
    archivo = request.files.get('file')

    if not clave or not periodo or not archivo:
        return jsonify({'error': 'Faltan campos: clave_cliente, periodo, file'}), 400
    if not _validate_periodo(periodo):
        return jsonify({'error': 'Formato de periodo inválido (use YYYY-YYYY)'}), 400

    ext = archivo.filename.rsplit('.', 1)[-1].lower() if archivo.filename else ''
    if ext not in ('xlsx', 'xls'):
        return jsonify({'error': 'El archivo debe ser Excel (.xlsx o .xls)'}), 400

    id_cliente = _get_client_id(clave)
    if id_cliente is None:
        return jsonify({'error': f'Cliente "{clave}" no encontrado'}), 404

    # Load valid SKUs — Excel catalog is primary; fall back to Odoo only when Excel is empty
    valid_skus = get_valid_skus()

    # Parse Excel
    try:
        content = archivo.read()
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        ws = wb.active
    except Exception as e:
        return jsonify({'error': f'No se pudo leer el archivo Excel: {str(e)}'}), 400

    # Find header row (row with 'SKU' in first column)
    header_row = None
    for r_idx in range(1, 10):
        val = ws.cell(row=r_idx, column=1).value
        if val and str(val).strip().upper() == 'SKU':
            header_row = r_idx
            break

    if header_row is None:
        return jsonify({'error': 'Estructura inválida: no se encontró fila de encabezado con "SKU"'}), 400

    # Map column names → indices
    col_map = {}
    for ci in range(1, ws.max_column + 1):
        h = ws.cell(row=header_row, column=ci).value
        if h:
            col_map[str(h).strip()] = ci

    required_headers = set(CAMPOS_INFO) | set(MESES_LABELS)
    missing = required_headers - set(col_map.keys())
    if missing:
        return jsonify({'error': f'Columnas faltantes en el archivo: {", ".join(sorted(missing))}'}), 400

    errors = []
    rows_to_save = []

    for r_idx in range(header_row + 1, ws.max_row + 1):
        sku = ws.cell(row=r_idx, column=col_map['SKU']).value
        if sku is None or str(sku).strip() == '':
            continue  # skip empty rows

        sku = str(sku).strip()

        # Validate SKU exists in catalog
        if sku not in valid_skus:
            errors.append(f'Fila {r_idx}: SKU "{sku}" no existe en el catálogo de productos')
            continue

        producto  = str(ws.cell(row=r_idx, column=col_map['Producto']).value or '').strip().upper()
        marca     = str(ws.cell(row=r_idx, column=col_map['Marca']).value or '').strip().upper() or 'N/A'
        modelo    = str(ws.cell(row=r_idx, column=col_map['Modelo']).value or '').strip().upper()
        color     = str(ws.cell(row=r_idx, column=col_map['Color']).value or '').strip().upper() or 'N/A'
        talla     = str(ws.cell(row=r_idx, column=col_map['Talla']).value or '').strip().upper() or 'N/A'

        month_values = {}
        month_error = False
        for mes_label, mes_col_name in zip(MESES, MESES_LABELS):
            raw = ws.cell(row=r_idx, column=col_map[mes_col_name]).value
            if raw is None or str(raw).strip() == '':
                raw = 0
            try:
                qty = int(float(str(raw)))
                if qty < 0:
                    errors.append(f'Fila {r_idx}, SKU {sku}: cantidad negativa en {mes_col_name}')
                    month_error = True
                    break
                month_values[mes_label] = qty
            except (ValueError, TypeError):
                errors.append(f'Fila {r_idx}, SKU {sku}: valor no numérico "{raw}" en {mes_col_name}')
                month_error = True
                break

        if month_error:
            continue

        rows_to_save.append({
            'sku':      sku,
            'producto': producto,
            'marca':    marca,
            'modelo':   modelo,
            'color':    color,
            'talla':    talla,
            **month_values,
        })

    if errors and not rows_to_save:
        return jsonify({'errores': errors, 'guardados': 0}), 422

    # Upsert rows
    saved = 0
    conn = obtener_conexion()
    cur = conn.cursor()
    try:
        for row in rows_to_save:
            cur.execute("""
                INSERT INTO forecast_proyecciones
                    (id_cliente, clave_cliente, periodo, sku, producto, marca, modelo,
                     color, talla, mayo, junio, julio, agosto, septiembre, octubre,
                     noviembre, diciembre, enero, febrero, marzo, abril)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    producto   = VALUES(producto),
                    marca      = VALUES(marca),
                    modelo     = VALUES(modelo),
                    color      = VALUES(color),
                    talla      = VALUES(talla),
                    mayo       = VALUES(mayo),
                    junio      = VALUES(junio),
                    julio      = VALUES(julio),
                    agosto     = VALUES(agosto),
                    septiembre = VALUES(septiembre),
                    octubre    = VALUES(octubre),
                    noviembre  = VALUES(noviembre),
                    diciembre  = VALUES(diciembre),
                    enero      = VALUES(enero),
                    febrero    = VALUES(febrero),
                    marzo      = VALUES(marzo),
                    abril      = VALUES(abril),
                    actualizado_en = CURRENT_TIMESTAMP
            """, (
                id_cliente, clave, periodo,
                row['sku'], row['producto'], row['marca'], row['modelo'],
                row['color'], row['talla'],
                row.get('mayo', 0), row.get('junio', 0), row.get('julio', 0),
                row.get('agosto', 0), row.get('septiembre', 0), row.get('octubre', 0),
                row.get('noviembre', 0), row.get('diciembre', 0), row.get('enero', 0),
                row.get('febrero', 0), row.get('marzo', 0), row.get('abril', 0),
            ))
            saved += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Error al guardar: {str(e)}'}), 500
    finally:
        cur.close()
        conn.close()

    result = {'guardados': saved}
    if errors:
        result['advertencias'] = errors
    return jsonify(result), 200


@forecast_bp.route('/forecast', methods=['GET'])
def listar_forecast():
    """
    GET /forecast?clave=<clave_cliente>&periodo=<periodo>
    Returns all forecast rows for a client+period.
    """
    clave  = request.args.get('clave', '').strip()
    periodo = request.args.get('periodo', '').strip()

    if not clave or not periodo:
        return jsonify({'error': 'Faltan parámetros: clave, periodo'}), 400

    conn = obtener_conexion()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT id, clave_cliente, periodo, sku, producto, marca, modelo, color, talla,
                   mayo, junio, julio, agosto, septiembre, octubre,
                   noviembre, diciembre, enero, febrero, marzo, abril,
                   (mayo+junio+julio+agosto+septiembre+octubre+
                    noviembre+diciembre+enero+febrero+marzo+abril) AS total,
                   actualizado_en
            FROM forecast_proyecciones
            WHERE clave_cliente = %s AND periodo = %s
            ORDER BY marca, modelo, sku
        """, (clave, periodo))
        rows = cur.fetchall()
        # Serialize datetime
        for r in rows:
            if r.get('actualizado_en'):
                r['actualizado_en'] = r['actualizado_en'].isoformat()
        return jsonify(rows), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


@forecast_bp.route('/forecast/periodos', methods=['GET'])
def listar_periodos():
    """
    GET /forecast/periodos?clave=<clave_cliente>
    Returns distinct periods available for a client.
    """
    clave = request.args.get('clave', '').strip()
    if not clave:
        return jsonify({'error': 'Falta parámetro clave'}), 400

    conn = obtener_conexion()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT DISTINCT periodo
            FROM forecast_proyecciones
            WHERE clave_cliente = %s
            ORDER BY periodo DESC
        """, (clave,))
        periodos = [r['periodo'] for r in cur.fetchall()]
        return jsonify(periodos), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


@forecast_bp.route('/forecast/avance', methods=['GET'])
def avance_forecast():
    """
    GET /forecast/avance?clave=<clave_cliente>&periodo=<periodo>

    Cross-reference: forecast quantities vs actual orders in the monitor table.
    Products are matched by normalizing SKU (stripping hyphens/spaces, uppercase),
    so clave_factura format (290189010) matches referencia_interna (290189-010).

    Returns a list of rows with:
      forecast_total, pedido_total, restante, pct_cubierto, estados (dict)
    """
    clave   = request.args.get('clave', '').strip()
    periodo = request.args.get('periodo', '').strip()

    if not clave or not periodo:
        return jsonify({'error': 'Faltan parámetros: clave, periodo'}), 400
    if not _validate_periodo(periodo):
        return jsonify({'error': 'Formato de periodo inválido'}), 400

    m = re.match(r'^(\d{4})-(\d{4})$', periodo)
    year1, year2 = int(m.group(1)), int(m.group(2))
    # Empezamos desde Jul del año anterior al periodo (igual que detalle_compras_odoo),
    # para capturar órdenes pre-temporada que el cliente coloca antes del 1 de mayo.
    # Ejemplo: periodo 2026-2027 → buscar órdenes desde 2025-07-01 hasta 2027-04-30.
    fecha_inicio = f'{year1 - 1}-07-01'
    fecha_fin    = f'{year2}-04-30'

    def _norm(s: str) -> str:
        """Remove hyphens/spaces, uppercase — for fuzzy SKU matching."""
        return re.sub(r'[\-\s]', '', str(s or '')).upper()

    conn = obtener_conexion()
    cur = conn.cursor(dictionary=True)
    try:
        # 1. Forecast rows for this client/period
        cur.execute("""
            SELECT id, sku, producto, marca, modelo, color, talla,
                   (mayo+junio+julio+agosto+septiembre+octubre+
                    noviembre+diciembre+enero+febrero+marzo+abril) AS forecast_total
            FROM forecast_proyecciones
            WHERE clave_cliente = %s AND periodo = %s
            ORDER BY marca, modelo, sku
        """, (clave, periodo))
        forecast_rows = cur.fetchall()

        if not forecast_rows:
            return jsonify([]), 200

        # 2. Build normalized SKU → canonical SKU map
        norm_to_sku: dict = {}
        for fr in forecast_rows:
            n = _norm(fr['sku'])
            if n:
                norm_to_sku[n] = fr['sku']

        # 3. Query Odoo sale.order.line — with in-memory cache (TTL = 3 min).
        #    This avoids repeating the slow XML-RPC round-trips on every tab switch.
        orders_by_sku: dict = {}
        _cache_key = (clave, periodo)
        _cached = _avance_cache.get(_cache_key)
        if _cached and (_time.time() - _cached[0]) < _AVANCE_TTL:
            orders_by_sku = _cached[1]
            logging.debug('avance_forecast: caché HIT para %s/%s', clave, periodo)
        else:
          try:
            from utils.odoo_utils import get_odoo_models, ODOO_DB, ODOO_PASSWORD
            uid_oo, models_oo, err_oo = get_odoo_models()
            if uid_oo and models_oo:
                # Find partner(s) matching the client reference code
                partner_ids = models_oo.execute_kw(
                    ODOO_DB, uid_oo, ODOO_PASSWORD,
                    'res.partner', 'search',
                    [[['ref', '=', clave]]]
                )
                if partner_ids:
                    # Get confirmed sale orders in the commercial period
                    order_ids = models_oo.execute_kw(
                        ODOO_DB, uid_oo, ODOO_PASSWORD,
                        'sale.order', 'search',
                        [[['partner_id', 'in', partner_ids],
                          ['state', 'in', ['sale', 'done']],
                          ['date_order', '>=', fecha_inicio],
                          ['date_order', '<=', fecha_fin + ' 23:59:59']]]
                    )
                    if order_ids:
                        # Read order lines
                        sol = models_oo.execute_kw(
                            ODOO_DB, uid_oo, ODOO_PASSWORD,
                            'sale.order.line', 'search_read',
                            [[['order_id', 'in', order_ids],
                              ['state', 'not in', ['cancel']]]],
                            {'fields': ['product_id', 'product_uom_qty',
                                        'order_id'], 'limit': 0}
                        )
                        # Batch-load default_codes for all referenced products
                        prod_ids = list({l['product_id'][0]
                                         for l in sol if l.get('product_id')})
                        prods = models_oo.execute_kw(
                            ODOO_DB, uid_oo, ODOO_PASSWORD,
                            'product.product', 'search_read',
                            [[['id', 'in', prod_ids]]],
                            {'fields': ['id', 'default_code'], 'limit': 0}
                        )
                        prod_code_map = {
                            p['id']: (p.get('default_code') or '').strip() or f'ODOO:{p["id"]}'
                            for p in prods
                        }
                        # Aggregate quantities per forecast SKU
                        for l in sol:
                            pid = l['product_id'][0] if l.get('product_id') else None
                            dc  = prod_code_map.get(pid, '')
                            matched = norm_to_sku.get(_norm(dc))
                            if matched is None:
                                continue
                            qty = int(l.get('product_uom_qty') or 0)
                            if matched not in orders_by_sku:
                                orders_by_sku[matched] = {'pedido_total': 0,
                                                          'estados': {}}
                            orders_by_sku[matched]['pedido_total'] += qty
                            orders_by_sku[matched]['estados']['Orden Confirmada'] = (
                                orders_by_sku[matched]['estados'].get(
                                    'Orden Confirmada', 0) + qty
                            )
            else:
                logging.warning('avance_forecast: no se pudo conectar a Odoo – %s', err_oo)
            # Guardar en caché (aunque esté vacío, para no repetir en fallo)
            _avance_cache[_cache_key] = (_time.time(), orders_by_sku)
          except Exception as _ex_oo:
            logging.exception('avance_forecast: error al consultar Odoo: %s', _ex_oo)

        # 4. Build result merging forecast + orders
        result = []
        for fr in forecast_rows:
            sku           = fr['sku']
            ord_data      = orders_by_sku.get(sku, {'pedido_total': 0, 'estados': {}})
            forecast_total = int(fr['forecast_total'] or 0)
            pedido_total   = ord_data['pedido_total']
            restante       = max(0, forecast_total - pedido_total)
            pct            = (round(pedido_total / forecast_total * 1000) / 10
                               if forecast_total > 0 else 0)
            result.append({
                'id':            fr['id'],
                'sku':           sku,
                'producto':      fr['producto'],
                'marca':         fr['marca'],
                'modelo':        fr['modelo'],
                'color':         fr['color'],
                'talla':         fr['talla'],
                'forecast_total': forecast_total,
                'pedido_total':   pedido_total,
                'restante':       restante,
                'pct_cubierto':   pct,
                'estados':        ord_data['estados'],
            })

        return jsonify(result), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


@forecast_bp.route('/forecast/sync-catalogo', methods=['POST'])
def sync_catalogo():
    """
    POST /forecast/sync-catalogo
    Manually trigger a re-sync of the Odoo product catalog into odoo_catalogo.
    Accepts optional JSON body: {"force": true} to re-sync even if already populated.
    """
    body  = request.get_json(silent=True) or {}
    force = bool(body.get('force', True))
    result = _trigger_catalogo_sync(force=force)
    return jsonify({'status': result}), 200


@forecast_bp.route('/forecast/sync-catalogo', methods=['GET'])
def sync_catalogo_status():
    """GET /forecast/sync-catalogo — returns catalog row count and sync status."""
    conn = obtener_conexion()
    cur  = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM odoo_catalogo')
    cnt = cur.fetchone()[0]
    cur.close()
    conn.close()
    return jsonify({
        'total_productos': cnt,
        'syncing': _catalogo_syncing,
    }), 200


@forecast_bp.route('/forecast/<int:fid>', methods=['PUT'])
def actualizar_forecast(fid):
    """
    PUT /forecast/<id>
    Body: {mayo, junio, ..., abril}
    Updates monthly quantities for a single row.
    """
    data = request.get_json(force=True, silent=True) or {}

    updates = {}
    for mes in MESES:
        if mes in data:
            try:
                qty = int(data[mes])
                if qty < 0:
                    return jsonify({'error': f'Cantidad negativa para {mes}'}), 400
                updates[mes] = qty
            except (ValueError, TypeError):
                return jsonify({'error': f'Valor inválido para {mes}'}), 400

    if not updates:
        # Also allow full row update (adding new product line)
        new_data = {}
        for field in ['producto', 'marca', 'modelo', 'color', 'talla']:
            if field in data:
                new_data[field] = str(data[field])[:255]
        for mes in MESES:
            new_data[mes] = int(data.get(mes, 0))
        updates = new_data

    if not updates:
        return jsonify({'error': 'Sin campos para actualizar'}), 400

    set_clause = ', '.join(f'{k} = %s' for k in updates)
    values = list(updates.values()) + [fid]

    conn = obtener_conexion()
    cur = conn.cursor()
    try:
        cur.execute(f"UPDATE forecast_proyecciones SET {set_clause} WHERE id = %s", values)
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({'error': 'Registro no encontrado'}), 404
        return jsonify({'ok': True}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


_SEARCH_PAGE = 50

# Alias map for Spanish plural/variant forms that don't match DB names
_SEARCH_ALIAS = {
    'zapatillas': 'zapatos',
    'zapatilla':  'zapatos',
    'tenis':      'zapatos',
    'calzado':    'zapatos',
    'calzados':   'zapatos',
    'anforas':    'anfora',
    'anfora':     'anfora',
    'anforitas':  'anfora',
    'bidones':    'bidon',
    'llantas':    'llanta',
    'luces':      'luz',
    'frenos':     'freno',
    'pedales':    'pedal',
    'guantes':    'guante',
    'rodilleras': 'rodillera',
    'coderas':    'codera',
    'gafas':      'gafa',
    'lentes':     'lente',
    'mochilas':   'mochila',
    'bolsos':     'bolso',
    'gorras':     'gorra',
    'cascos':     'casco',
}


def _normalizar_query(q: str) -> str:
    """Return a normalized search term that better matches DB naming conventions."""
    lower = q.lower()
    if lower in _SEARCH_ALIAS:
        return _SEARCH_ALIAS[lower]
    # Strip common Spanish plural 's' for words longer than 5 chars
    if lower.endswith('s') and len(lower) > 5:
        return q[:-1]
    return q


@forecast_bp.route('/forecast/catalogo-excel', methods=['POST'])
def cargar_catalogo_excel():
    """
    POST /forecast/catalogo-excel  (multipart/form-data)
    Field: file (xlsx/xls) con columnas: SKU, NOMBRE, [COLOR], [TALLA]
    Carga los productos en forecast_excel_productos para usarse como catálogo
    de validación y búsqueda en lugar de Odoo.
    """
    if not OPENPYXL_OK:
        return jsonify({'error': 'openpyxl no instalado en el servidor'}), 500

    archivo = request.files.get('file')
    if not archivo:
        return jsonify({'error': 'Falta el archivo (field: file)'}), 400

    ext = archivo.filename.rsplit('.', 1)[-1].lower() if archivo.filename else ''
    if ext not in ('xlsx', 'xls'):
        return jsonify({'error': 'El archivo debe ser Excel (.xlsx o .xls)'}), 400

    content = archivo.read()
    result = load_excel_products(content)

    if not result['success']:
        return jsonify({'error': result.get('message', 'Error al procesar el archivo')}), 422

    return jsonify({
        'cargados':                 result['cargados'],
        'total_filas_procesadas':   result['total_filas_procesadas'],
        'duplicados_actualizados':  result['duplicados_actualizados'],
        'advertencias':             result.get('errores', []),
    }), 200


@forecast_bp.route('/forecast/catalogo-excel', methods=['GET'])
def estado_catalogo_excel():
    """GET /forecast/catalogo-excel — total de productos cargados desde Excel."""
    conn = obtener_conexion()
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM forecast_excel_productos WHERE origen = 'excel'")
    cnt = cur.fetchone()[0]
    cur.close()
    conn.close()
    return jsonify({'total_productos': cnt}), 200


@forecast_bp.route('/forecast/catalogo-excel/lista', methods=['GET'])
def listar_catalogo_excel():
    """
    GET /forecast/catalogo-excel/lista?q=<search>&limit=<int>&offset=<int>
    Paginates products from the Excel catalog.
    """
    q      = request.args.get('q', '').strip()
    try:
        limit  = min(int(request.args.get('limit', 50)), 500)
        offset = max(int(request.args.get('offset', 0)), 0)
    except (ValueError, TypeError):
        limit, offset = 50, 0

    result = list_excel_products(search=q, limit=limit, offset=offset)
    for p in result['productos']:
        if p.get('cargado_en'):
            p['cargado_en'] = p['cargado_en'].isoformat() if hasattr(p['cargado_en'], 'isoformat') else str(p['cargado_en'])
        if p.get('actualizado_en'):
            p['actualizado_en'] = p['actualizado_en'].isoformat() if hasattr(p['actualizado_en'], 'isoformat') else str(p['actualizado_en'])
    return jsonify(result), 200


@forecast_bp.route('/forecast/catalogo-excel', methods=['DELETE'])
def limpiar_catalogo_excel():
    """DELETE /forecast/catalogo-excel — elimina todos los productos del catálogo Excel."""
    result = clear_excel_catalog()
    if 'message' in result and 'Error' in result.get('message', ''):
        return jsonify({'error': result['message']}), 500
    return jsonify(result), 200


@forecast_bp.route('/forecast/buscar-producto', methods=['GET'])
def buscar_producto():
    """
    GET /forecast/buscar-producto?q=<query>&offset=<int>
    Searches forecast_excel_productos (Excel catalog, primary source).
    Falls back to odoo_catalogo when Excel catalog is empty,
    and to monitor table if neither is populated.
    Returns {results: [...], has_more: bool, offset: int} with up to 50 items per page.
    """
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'results': [], 'has_more': False, 'offset': 0}), 200

    try:
        offset = max(0, int(request.args.get('offset', 0)))
    except (ValueError, TypeError):
        offset = 0

    q_search = _normalizar_query(q)
    like = f'%{q_search}%'
    conn = obtener_conexion()
    cur = conn.cursor(dictionary=True)
    try:
        # Decide source: Excel catalog takes priority
        cur.execute("SELECT COUNT(*) as cnt FROM forecast_excel_productos WHERE origen = 'excel'")
        use_excel = cur.fetchone()['cnt'] > 0

        if use_excel:
            cur.execute("""
                SELECT sku, nombre AS nombre_src, color AS odoo_color, talla AS odoo_talla
                FROM forecast_excel_productos
                WHERE origen = 'excel'
                  AND (sku LIKE %s OR nombre LIKE %s)
                ORDER BY
                    CASE WHEN sku = %s THEN 0 ELSE 1 END,
                    nombre
                LIMIT %s OFFSET %s
            """, (like, like, q_search, _SEARCH_PAGE + 1, offset))
            rows = cur.fetchall()
            has_more = len(rows) > _SEARCH_PAGE
            rows = rows[:_SEARCH_PAGE]

            results = []
            for r in rows:
                color = (r.get('odoo_color') or '').strip().upper() or 'N/A'
                talla = (r.get('odoo_talla') or '').strip().upper() or 'N/A'
                nombre = (r.get('nombre_src') or '').strip().upper()
                results.append({
                    'sku':      r['sku'] or '',
                    'producto': nombre,
                    'marca':    'N/A',
                    'modelo':   '',
                    'color':    color,
                    'talla':    talla,
                    'label':    f"{r['sku']} — {nombre}",
                })
            return jsonify({'results': results, 'has_more': has_more, 'offset': offset}), 200

        # Fallback: odoo_catalogo
        cur.execute('SELECT COUNT(*) as cnt FROM odoo_catalogo')
        use_catalogo = cur.fetchone()['cnt'] > 0

        if use_catalogo:
            cur.execute("""
                SELECT
                    oc.referencia_interna                                       AS sku,
                    oc.nombre_producto                                          AS nombre_src,
                    oc.categoria                                                AS categoria,
                    oc.marca                                                    AS marca,
                    oc.color                                                    AS odoo_color,
                    oc.talla                                                    AS odoo_talla,
                    pv.descripcion                                              AS descripcion_pv,
                    pv.modelo                                                   AS modelo_pv
                FROM odoo_catalogo oc
                LEFT JOIN proyecciones_ventas pv ON pv.clave_odoo = oc.referencia_interna
                WHERE (
                    oc.nombre_producto    LIKE %s
                    OR oc.referencia_interna LIKE %s
                    OR oc.marca           LIKE %s
                    OR oc.categoria       LIKE %s
                    OR pv.descripcion     LIKE %s
                    OR pv.modelo          LIKE %s
                    OR pv.clave_factura   LIKE %s
                )
                ORDER BY
                    CASE WHEN oc.referencia_interna = %s THEN 0 ELSE 1 END,
                    oc.nombre_producto
                LIMIT %s OFFSET %s
            """, (like, like, like, like, like, like, like, q_search, _SEARCH_PAGE + 1, offset))
        else:
            # Last fallback: monitor table (only invoiced products)
            cur.execute("""
                SELECT
                    m.referencia_interna                                            AS sku,
                    ANY_VALUE(m.nombre_producto)                                    AS nombre_src,
                    ANY_VALUE(m.categoria_producto)                                 AS categoria,
                    ANY_VALUE(m.marca)                                              AS marca,
                    ANY_VALUE(pv.descripcion)                                       AS descripcion_pv,
                    ANY_VALUE(pv.modelo)                                            AS modelo_pv
                FROM monitor m
                LEFT JOIN proyecciones_ventas pv ON pv.clave_odoo = m.referencia_interna
                WHERE m.referencia_interna IS NOT NULL
                  AND m.referencia_interna != ''
                  AND (
                      m.nombre_producto    LIKE %s
                      OR m.referencia_interna LIKE %s
                      OR m.marca           LIKE %s
                      OR pv.descripcion    LIKE %s
                      OR pv.modelo         LIKE %s
                      OR pv.clave_factura  LIKE %s
                  )
                GROUP BY m.referencia_interna
                ORDER BY
                    CASE WHEN m.referencia_interna = %s THEN 0 ELSE 1 END,
                    ANY_VALUE(m.nombre_producto)
                LIMIT %s OFFSET %s
            """, (like, like, like, like, like, like, q_search, _SEARCH_PAGE + 1, offset))

        rows = cur.fetchall()
        has_more = len(rows) > _SEARCH_PAGE
        rows = rows[:_SEARCH_PAGE]

        results = []
        for r in rows:
            odoo_color = (r.get('odoo_color') or '').strip().upper()
            odoo_talla = (r.get('odoo_talla') or '').strip().upper()

            if not odoo_color and r.get('nombre_src'):
                _nombre_raw = re.sub(r'^\d{5,}\s+', '', (r['nombre_src'] or '').upper().strip())
                _paren = re.search(r'\(([^)]+)\)\s*$', _nombre_raw)
                if _paren:
                    odoo_color = _paren.group(1).strip()

            if odoo_color:
                color = odoo_color
                talla = odoo_talla
                if r.get('descripcion_pv'):
                    _, talla_pv = _parse_color_talla(r['descripcion_pv'], r.get('modelo_pv') or '')
                    if not talla:
                        talla = talla_pv
                    producto = _clean_producto(r['descripcion_pv'], color, talla_pv).upper()
                    modelo   = (r.get('modelo_pv') or '').upper()
                else:
                    raw = re.sub(r'^\d{5,}\s+', '', (r['nombre_src'] or '').upper().strip())
                    brand_up = (r.get('marca') or '').upper().strip()
                    if brand_up:
                        raw = re.sub(r'\b' + re.escape(brand_up) + r'\b\s*', '', raw).strip()
                    raw = re.sub(r'\s*\([^)]*\)\s*$', '', raw).strip()
                    categoria   = (r.get('categoria') or '')
                    modelo_hint = categoria.split(' / ')[-1].strip().upper() if ' / ' in categoria else ''
                    producto = _clean_producto(raw, color, talla)
                    modelo   = modelo_hint
            elif r.get('descripcion_pv'):
                color, talla = _parse_color_talla(r['descripcion_pv'], r.get('modelo_pv') or '')
                producto = _clean_producto(r['descripcion_pv'], color, talla).upper()
                modelo   = (r.get('modelo_pv') or '').upper()
            else:
                raw = re.sub(r'^\d{5,}\s+', '', (r['nombre_src'] or '').upper().strip())
                brand_up = (r.get('marca') or '').upper().strip()
                if brand_up:
                    raw = re.sub(r'\b' + re.escape(brand_up) + r'\b\s*', '', raw).strip()
                categoria   = (r.get('categoria') or '')
                modelo_hint = categoria.split(' / ')[-1].strip().upper() if ' / ' in categoria else ''
                paren_match = re.search(r'\(([^)]+)\)\s*$', raw)
                if paren_match:
                    color = paren_match.group(1).strip()
                    clean_raw = raw[:paren_match.start()].strip()
                    talla = ''
                    producto = _clean_producto(clean_raw, '', '')
                else:
                    color, talla = _parse_color_talla(raw, modelo_hint)
                    producto = _clean_producto(raw, color, talla)
                modelo   = modelo_hint

            results.append({
                'sku':      r['sku'] or '',
                'producto': producto,
                'marca':    (r.get('marca') or '').upper() or 'N/A',
                'modelo':   modelo,
                'color':    color.upper() or 'N/A',
                'talla':    talla.upper() or 'N/A',
                'label':    f"{r['sku']} — {producto}",
            })
        return jsonify({'results': results, 'has_more': has_more, 'offset': offset}), 200
    finally:
        cur.close()
        conn.close()


@forecast_bp.route('/forecast/<int:fid>', methods=['DELETE'])
def eliminar_forecast(fid):
    """DELETE /forecast/<id>"""
    conn = obtener_conexion()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM forecast_proyecciones WHERE id = %s", (fid,))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({'error': 'Registro no encontrado'}), 404
        return jsonify({'ok': True}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


@forecast_bp.route('/forecast/guardar', methods=['POST'])
def guardar_forecast():
    """
    POST /forecast/guardar
    Body: {clave_cliente, id_cliente, periodo, rows: [{sku, producto, marca, modelo,
           color, talla, mayo, ..., abril}]}
    Batch upsert – used from edit mode in frontend.
    """
    data = request.get_json(force=True, silent=True) or {}
    clave      = str(data.get('clave_cliente', '')).strip()
    id_cliente = data.get('id_cliente')
    periodo    = str(data.get('periodo', '')).strip()
    rows       = data.get('rows', [])

    if not clave or not id_cliente or not periodo:
        return jsonify({'error': 'Faltan campos: clave_cliente, id_cliente, periodo'}), 400
    if not _validate_periodo(periodo):
        return jsonify({'error': 'Formato de periodo inválido'}), 400
    if not isinstance(rows, list) or len(rows) == 0:
        return jsonify({'error': 'rows debe ser una lista no vacía'}), 400

    # Validate all SKUs exist in forecast_excel_productos (priority) + odoo_catalogo, monitor, proyecciones_ventas (fallback)
    # Aceptamos SKUs que existan en cualquiera de estas fuentes
    valid_skus = get_valid_skus()

    errors = []
    valid_rows = []
    for i, row in enumerate(rows):
        sku = str(row.get('sku', '')).strip()
        if not sku:
            errors.append(f'Fila {i+1}: SKU vacío')
            continue
        
        # Validar cantidades primero
        month_vals = {}
        month_valid = True
        for mes in MESES:
            try:
                qty = int(row.get(mes, 0))
                if qty < 0:
                    raise ValueError()
                month_vals[mes] = qty
            except (ValueError, TypeError):
                errors.append(f'Fila {i+1}, SKU {sku}: cantidad inválida para {mes}')
                month_valid = False
                break
        
        if not month_valid:
            continue
        
        # Validar SKU: aceptar si existe en cualquier tabla fuente O si tiene metadata de Odoo
        has_requiredMetadata = (
            row.get('producto', '').strip() and  # producto no vacío
            row.get('marca', '').strip() and       # marca no vacío
            row.get('modelo', '').strip() and      # modelo no vacío
            row.get('color', '').strip() and       # color no vacío
            row.get('talla', '').strip()           # talla no vacío
        )
        
        if sku not in valid_skus and not has_requiredMetadata:
            errors.append(f'Fila {i+1}: SKU "{sku}" no existe en el catálogo. Selecciona un producto válido desde el modal de búsqueda.')
            continue
        
        valid_rows.append({
            'sku':      sku,
            'producto': str(row.get('producto', '')).strip().upper()[:255],
            'marca':    (str(row.get('marca', '')).strip().upper() or 'N/A')[:100],
            'modelo':   str(row.get('modelo', '')).strip().upper()[:100],
            'color':    (str(row.get('color', '')).strip().upper() or 'N/A')[:100],
            'talla':    (str(row.get('talla', '')).strip().upper() or 'N/A')[:50],
            **month_vals,
        })

    if errors and not valid_rows:
        return jsonify({'errores': errors, 'guardados': 0}), 422

    saved = 0
    conn = obtener_conexion()
    cur = conn.cursor()
    try:
        for row in valid_rows:
            cur.execute("""
                INSERT INTO forecast_proyecciones
                    (id_cliente, clave_cliente, periodo, sku, producto, marca, modelo,
                     color, talla, mayo, junio, julio, agosto, septiembre, octubre,
                     noviembre, diciembre, enero, febrero, marzo, abril)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    producto   = VALUES(producto),
                    marca      = VALUES(marca),
                    modelo     = VALUES(modelo),
                    color      = VALUES(color),
                    talla      = VALUES(talla),
                    mayo       = VALUES(mayo),
                    junio      = VALUES(junio),
                    julio      = VALUES(julio),
                    agosto     = VALUES(agosto),
                    septiembre = VALUES(septiembre),
                    octubre    = VALUES(octubre),
                    noviembre  = VALUES(noviembre),
                    diciembre  = VALUES(diciembre),
                    enero      = VALUES(enero),
                    febrero    = VALUES(febrero),
                    marzo      = VALUES(marzo),
                    abril      = VALUES(abril),
                    actualizado_en = CURRENT_TIMESTAMP
            """, (
                int(id_cliente), clave, periodo,
                row['sku'], row['producto'], row['marca'], row['modelo'],
                row['color'], row['talla'],
                row['mayo'], row['junio'], row['julio'], row['agosto'],
                row['septiembre'], row['octubre'], row['noviembre'], row['diciembre'],
                row['enero'], row['febrero'], row['marzo'], row['abril'],
            ))
            saved += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Error al guardar: {str(e)}'}), 500
    finally:
        cur.close()
        conn.close()

    result = {'guardados': saved}
    if errors:
        result['advertencias'] = errors
    return jsonify(result), 200
