from flask import Blueprint, jsonify
from models.monitor_odoo_model import obtener_todos_los_registros

previo_bp = Blueprint('previo', __name__, url_prefix='')


@previo_bp.route('/monitor_odoo_calculado', methods=['GET'])
def monitor_calculado():
    datos = obtener_todos_los_registros()
    resultados = []

    for factura in datos:
        try:
            numero_factura = factura.get('numero_factura')
            fecha_factura = factura.get('fecha_factura')
            categoria = factura.get('categoria_producto') or ''

            # === FILTROS ===
            if not numero_factura or numero_factura == '/':
                continue
            if not fecha_factura or fecha_factura == '0001-01-01 00:00:00':
                continue
            if not categoria.strip():  # Si está vacía o solo espacios
                continue
            if categoria.strip().upper() == 'SERVICIOS':
                continue

            # === CÁLCULOS ===
            precio = float(factura.get('precio_unitario') or 0)
            cantidad = float(factura.get('cantidad') or 0)
            estado = (factura.get('estado_factura') or '').lower().replace(' ', '')

            venta_total = precio * cantidad * 1.16
            venta_total = -venta_total if estado == 'cancel' else venta_total

            partes = categoria.split(' /')
            marca = partes[0] if len(partes) >= 1 else categoria
            subcategoria = partes[1] if len(partes) >= 2 else ''
            contiene_eride = 'SI' if 'ERIDE' in categoria.upper() else 'NO'
            contiene_apparel = 'SI' if 'APPAREL' in categoria.upper() else 'NO'

            resultados.append({
                **factura,
                "venta_total": round(venta_total, 2),
                "marca": marca,
                "subcategoria": subcategoria,
                "eride": contiene_eride,
                "apparel": contiene_apparel
            })

        except Exception as e:
            print("Error procesando factura:", factura.get("numero_factura", "???"), str(e))
            continue

    return jsonify(resultados)
