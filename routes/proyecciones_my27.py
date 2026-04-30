"""
Módulo: Proyecciones MY27
Vista consolidada de los 92 artículos MY27 con cantidades por mes
sumando todas las proyecciones de todos los distribuidores.
"""

import io
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file

from db_conexion import obtener_conexion
from routes.forecast import SKU_CATALOG, FORECAST_SKU_WHITELIST

try:
    import openpyxl
    from openpyxl.styles import (
        Alignment, Border, Font, PatternFill, Side
    )
    from openpyxl.utils import get_column_letter
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False

proyecciones_my27_bp = Blueprint('proyecciones_my27', __name__, url_prefix='/proyecciones-my27')

MESES       = ['mayo', 'junio', 'julio', 'agosto', 'septiembre',
               'octubre', 'noviembre', 'diciembre', 'enero', 'febrero', 'marzo', 'abril']
MESES_LABEL = ['May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic', 'Ene', 'Feb', 'Mar', 'Abr']


# ─────────────────────────────────────────────────────────────────────────────
# Helper: obtener datos consolidados
# ─────────────────────────────────────────────────────────────────────────────

def _get_datos_consolidados(periodo: str = '') -> dict:
    """
    Consulta la BD y devuelve los 92 artículos con sumas por mes
    de todos los distribuidores y el desglose individual.
    """
    conn = obtener_conexion()
    cur  = conn.cursor(dictionary=True)

    where  = "WHERE periodo = %s" if periodo else ""
    params = (periodo,) if periodo else ()

    try:
        # Totales por SKU
        cur.execute(f"""
            SELECT
                sku,
                MAX(producto)   AS producto,
                MAX(marca)      AS marca,
                MAX(modelo)     AS modelo,
                MAX(color)      AS color,
                MAX(talla)      AS talla,
                SUM(mayo)       AS mayo,
                SUM(junio)      AS junio,
                SUM(julio)      AS julio,
                SUM(agosto)     AS agosto,
                SUM(septiembre) AS septiembre,
                SUM(octubre)    AS octubre,
                SUM(noviembre)  AS noviembre,
                SUM(diciembre)  AS diciembre,
                SUM(enero)      AS enero,
                SUM(febrero)    AS febrero,
                SUM(marzo)      AS marzo,
                SUM(abril)      AS abril,
                SUM(mayo+junio+julio+agosto+septiembre+
                    octubre+noviembre+diciembre+
                    enero+febrero+marzo+abril) AS total_anual,
                COUNT(DISTINCT clave_cliente)  AS num_distribuidores
            FROM forecast_proyecciones
            {where}
            GROUP BY sku
        """, params)
        totales_map = {r['sku']: r for r in cur.fetchall()}

        # Desglose por SKU + distribuidor (incluye nombre_cliente)
        where_fp = "WHERE fp.periodo = %s" if periodo else ""
        cur.execute(f"""
            SELECT
                fp.sku, fp.clave_cliente,
                COALESCE(c.nombre_cliente, fp.clave_cliente) AS nombre_cliente,
                fp.mayo, fp.junio, fp.julio, fp.agosto, fp.septiembre,
                fp.octubre, fp.noviembre, fp.diciembre,
                fp.enero, fp.febrero, fp.marzo, fp.abril,
                (fp.mayo+fp.junio+fp.julio+fp.agosto+fp.septiembre+
                 fp.octubre+fp.noviembre+fp.diciembre+
                 fp.enero+fp.febrero+fp.marzo+fp.abril) AS total_dist
            FROM forecast_proyecciones fp
            LEFT JOIN clientes c ON c.clave = fp.clave_cliente
            {where_fp}
            ORDER BY fp.sku, fp.clave_cliente
        """, params)
        desglose_map: dict = {}
        for fd in cur.fetchall():
            s = fd['sku']
            if s not in desglose_map:
                desglose_map[s] = []
            desglose_map[s].append({
                'clave_cliente':  fd['clave_cliente'],
                'nombre_cliente': fd['nombre_cliente'],
                'total':          int(fd['total_dist'] or 0),
                'meses':          {mes: int(fd[mes] or 0) for mes in MESES},
            })

        # Construir los 92 artículos
        articulos = []
        for sku in FORECAST_SKU_WHITELIST:
            cat_info  = SKU_CATALOG.get(sku, {})
            avail_map = cat_info.get('avail', {})
            precios   = cat_info.get('prices', {})
            t         = totales_map.get(sku)

            meses_data = {
                mes: {
                    'cantidad':   int(t[mes] or 0) if t else 0,
                    'disponible': avail_map.get(mes, True),
                }
                for mes in MESES
            }

            articulos.append({
                'sku':               sku,
                'producto':          (t['producto'] or '') if t else '',
                'marca':             (t['marca']    or '') if t else '',
                'modelo':            (t['modelo']   or '') if t else '',
                'color':             (t['color']    or '') if t else '',
                'talla':             (t['talla']    or '') if t else '',
                'precio_dist':       float(precios.get('Distribuidor', 0)),
                'num_distribuidores': int(t['num_distribuidores'] or 0) if t else 0,
                'total_anual':       int(t['total_anual'] or 0) if t else 0,
                'meses':             meses_data,
                'desglose':          desglose_map.get(sku, []),
            })

        totales_mes   = {mes: sum(a['meses'][mes]['cantidad'] for a in articulos) for mes in MESES}
        total_general = sum(totales_mes.values())

        distribuidores_activos = {
            d['clave_cliente']
            for a in articulos
            for d in a['desglose']
            if d['total'] > 0
        }

        return {
            'articulos':    articulos,
            'totales_mes':  totales_mes,
            'total_general': total_general,
            'kpis': {
                'total_articulos':        len(articulos),
                'articulos_con_pedido':   sum(1 for a in articulos if a['total_anual'] > 0),
                'articulos_sin_pedido':   sum(1 for a in articulos if a['total_anual'] == 0),
                'total_unidades':         total_general,
                'distribuidores_activos': len(distribuidores_activos),
            },
            'meses':        MESES,
            'meses_labels': MESES_LABEL,
            'periodo':      periodo or '2026-2027',
            'generado_en':  datetime.now().strftime('%d/%m/%Y %H:%M'),
        }

    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# GET /proyecciones-my27  — datos JSON
# ─────────────────────────────────────────────────────────────────────────────

@proyecciones_my27_bp.route('', methods=['GET'])
def listar():
    """
    Retorna los 92 artículos MY27 con cantidades consolidadas por mes.
    Query param: ?periodo=2026-2027
    """
    try:
        periodo = request.args.get('periodo', '2026-2027').strip()
        data    = _get_datos_consolidados(periodo)
        return jsonify(data), 200
    except Exception as e:
        logging.exception('[proyecciones_my27] listar error: %s', e)
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# GET /proyecciones-my27/exportar  — descarga Excel
# ─────────────────────────────────────────────────────────────────────────────

@proyecciones_my27_bp.route('/exportar', methods=['GET'])
def exportar_excel():
    """
    Exporta el resumen de proyecciones MY27 a Excel con formato profesional.
    Query param: ?periodo=2026-2027
    """
    if not OPENPYXL_OK:
        return jsonify({'error': 'openpyxl no disponible'}), 500

    try:
        periodo = request.args.get('periodo', '2026-2027').strip()
        data    = _get_datos_consolidados(periodo)
        excel   = _generar_excel(data)

        nombre  = f"ProyeccionesMY27_{periodo}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        buf     = io.BytesIO(excel)
        buf.seek(0)

        return send_file(
            buf,
            as_attachment=True,
            download_name=nombre,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
    except Exception as e:
        logging.exception('[proyecciones_my27] exportar error: %s', e)
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Helper: generar Excel
# ─────────────────────────────────────────────────────────────────────────────

def _generar_excel(data: dict) -> bytes:
    wb = openpyxl.Workbook()

    # ── Hoja 1: Resumen consolidado ──────────────────────────────────────────
    ws = wb.active
    ws.title = 'Resumen MY27'

    # Colores
    AZUL_OSCURO = 'FF1A3C5E'
    AZUL_MED    = 'FF2E6DA4'
    GRIS_CLARO  = 'FFF2F2F2'
    NARANJA     = 'FFFF6B00'
    VERDE       = 'FF1E8449'
    ROJO        = 'FFC0392B'
    BLANCO      = 'FFFFFFFF'

    def cell_style(cell, bold=False, bg=None, fg='FF000000',
                   size=10, center=False, wrap=False, border=False):
        cell.font      = Font(bold=bold, color=fg, size=size, name='Calibri')
        cell.alignment = Alignment(
            horizontal='center' if center else 'left',
            vertical='center',
            wrap_text=wrap,
        )
        if bg:
            cell.fill = PatternFill('solid', fgColor=bg)
        if border:
            thin = Side(style='thin', color='FFD0D0D0')
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)

    thin_side = Side(style='thin', color='FFD0D0D0')
    thin_bdr  = Border(left=thin_side, right=thin_side,
                       top=thin_side,  bottom=thin_side)

    # ── Título principal ─────────────────────────────────────────────────────
    ws.merge_cells('A1:S1')
    titulo = ws['A1']
    titulo.value = f"PROYECCIONES MY27  |  Periodo: {data['periodo']}  |  Generado: {data['generado_en']}"
    cell_style(titulo, bold=True, bg=AZUL_OSCURO, fg=BLANCO, size=13, center=True)
    ws.row_dimensions[1].height = 30

    # ── KPIs fila 2 ─────────────────────────────────────────────────────────
    kpis = data['kpis']
    kpi_datos = [
        ('Total artículos',       kpis['total_articulos']),
        ('Con proyección',        kpis['articulos_con_pedido']),
        ('Sin proyección',        kpis['articulos_sin_pedido']),
        ('Total unidades',        kpis['total_unidades']),
        ('Distribuidores activos', kpis['distribuidores_activos']),
    ]
    col_kpi = 1
    for label, valor in kpi_datos:
        ws.merge_cells(
            start_row=2, start_column=col_kpi,
            end_row=2,   end_column=col_kpi + 2
        )
        c = ws.cell(row=2, column=col_kpi, value=f"{label}: {valor}")
        cell_style(c, bold=True, bg=AZUL_MED, fg=BLANCO, size=10, center=True)
        col_kpi += 3
    ws.row_dimensions[2].height = 22

    # ── Encabezados tabla (fila 4) ───────────────────────────────────────────
    encabezados = ['SKU', 'Producto', 'Marca', 'Modelo', 'Color', 'Talla'] + \
                  MESES_LABEL + ['TOTAL AÑO']

    for ci, enc in enumerate(encabezados, start=1):
        c = ws.cell(row=4, column=ci, value=enc)
        cell_style(c, bold=True, bg=AZUL_OSCURO, fg=BLANCO, size=10, center=True)
        c.border = thin_bdr
    ws.row_dimensions[4].height = 24

    # Fila de totales generales (fila 3, encima de datos)
    ws.cell(row=3, column=1, value='TOTALES').font = Font(bold=True, color=AZUL_OSCURO, size=10)
    for ci, mes in enumerate(MESES, start=7):
        c = ws.cell(row=3, column=ci, value=data['totales_mes'].get(mes, 0))
        cell_style(c, bold=True, bg=NARANJA, fg=BLANCO, size=10, center=True)
        c.border = thin_bdr
    c_tot = ws.cell(row=3, column=19, value=data['total_general'])
    cell_style(c_tot, bold=True, bg=NARANJA, fg=BLANCO, size=10, center=True)
    c_tot.border = thin_bdr
    ws.row_dimensions[3].height = 20

    # ── Datos: los 92 artículos ──────────────────────────────────────────────
    for ri, art in enumerate(data['articulos'], start=5):
        fila_par = (ri % 2 == 0)
        bg_fila  = GRIS_CLARO if fila_par else BLANCO

        valores = [
            art['sku'], art['producto'], art['marca'],
            art['modelo'], art['color'], art['talla'],
        ]
        for ci, val in enumerate(valores, start=1):
            c = ws.cell(row=ri, column=ci, value=val)
            cell_style(c, bg=bg_fila, size=9, border=True)
            c.border = thin_bdr

        total_fila = 0
        for ci, mes in enumerate(MESES, start=7):
            cant = art['meses'][mes]['cantidad']
            disp = art['meses'][mes]['disponible']
            c    = ws.cell(row=ri, column=ci, value=cant if cant > 0 else '')
            total_fila += cant

            if not disp:
                cell_style(c, bg='FF2C2C2C', fg='FF2C2C2C', center=True, size=9)
            elif cant > 0:
                cell_style(c, bold=True, bg=VERDE, fg=BLANCO, center=True, size=9)
            else:
                cell_style(c, bg=bg_fila, center=True, size=9)
            c.border = thin_bdr

        # Total anual
        c_tot = ws.cell(row=ri, column=19, value=total_fila if total_fila > 0 else '')
        if total_fila > 0:
            cell_style(c_tot, bold=True, bg=AZUL_MED, fg=BLANCO, center=True, size=10)
        else:
            cell_style(c_tot, bg=bg_fila, center=True, size=9)
        c_tot.border = thin_bdr

        ws.row_dimensions[ri].height = 16

    # Anchos de columna
    anchos = [18, 35, 12, 20, 15, 8] + [6] * 12 + [10]
    for ci, ancho in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(ci)].width = ancho

    ws.freeze_panes = 'G5'

    # ── Hoja 2: Desglose por distribuidor ────────────────────────────────────
    ws2 = wb.create_sheet('Desglose Distribuidores')

    enc2 = ['SKU', 'Producto', 'Marca', 'Modelo', 'Color', 'Talla',
            'Distribuidor'] + MESES_LABEL + ['TOTAL']
    for ci, enc in enumerate(enc2, start=1):
        c = ws2.cell(row=1, column=ci, value=enc)
        cell_style(c, bold=True, bg=AZUL_OSCURO, fg=BLANCO, size=10, center=True)
        c.border = thin_bdr
    ws2.row_dimensions[1].height = 22

    ri2 = 2
    for art in data['articulos']:
        for dist in art['desglose']:
            if dist['total'] == 0:
                continue
            fila_par = (ri2 % 2 == 0)
            bg       = GRIS_CLARO if fila_par else BLANCO

            vals = [art['sku'], art['producto'], art['marca'],
                    art['modelo'], art['color'], art['talla'],
                    dist['clave_cliente']]
            for ci, v in enumerate(vals, start=1):
                c = ws2.cell(row=ri2, column=ci, value=v)
                cell_style(c, bg=bg, size=9)
                c.border = thin_bdr

            for ci, mes in enumerate(MESES, start=8):
                cant = dist['meses'].get(mes, 0)
                c    = ws2.cell(row=ri2, column=ci, value=cant if cant > 0 else '')
                if cant > 0:
                    cell_style(c, bold=True, bg=VERDE, fg=BLANCO, center=True, size=9)
                else:
                    cell_style(c, bg=bg, center=True, size=9)
                c.border = thin_bdr

            c_tot = ws2.cell(row=ri2, column=20, value=dist['total'] or '')
            cell_style(c_tot, bold=True, bg=AZUL_MED, fg=BLANCO, center=True, size=10)
            c_tot.border = thin_bdr
            ws2.row_dimensions[ri2].height = 16
            ri2 += 1

    anchos2 = [18, 35, 12, 20, 15, 8, 14] + [6] * 12 + [10]
    for ci, ancho in enumerate(anchos2, start=1):
        ws2.column_dimensions[get_column_letter(ci)].width = ancho
    ws2.freeze_panes = 'H2'

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
