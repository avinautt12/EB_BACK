from flask import Blueprint, jsonify, request, Response
from db_conexion import obtener_conexion
from decimal import Decimal
import json
from utils.email_utils import crear_cuerpo_email
from utils.odoo_utils import get_odoo_models, ODOO_DB, ODOO_PASSWORD
import logging
import traceback

caratulas_bp = Blueprint('caratulas', __name__, url_prefix='')

@caratulas_bp.route('/caratula_evac', methods=['GET'])
def buscar_caratula_evac():
    try:
        clave = request.args.get('clave')
        nombre_cliente = request.args.get('nombre_cliente')
        
        if not clave and not nombre_cliente:
            return jsonify({'error': 'Se requiere clave o nombre_cliente'}), 400

        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        
        nombre_a_buscar = nombre_cliente
        columna_a_buscar = "nombre_cliente" # Por defecto buscamos en nombre_cliente
        
        # Si la búsqueda es por nombre y contiene "Integral", es un grupo.
        if nombre_cliente and "integral" in nombre_cliente.lower():
            cursor.execute("SELECT id FROM grupo_clientes WHERE nombre_grupo = %s", (nombre_cliente,))
            grupo = cursor.fetchone()
            
            if grupo:
                # Si es un grupo, CAMBIAMOS la columna y el valor a buscar
                nombre_a_buscar = f"Integral {grupo['id']}"
                columna_a_buscar = "clave" # ¡Aquí está la magia!
                logging.info("Búsqueda de GRUPO: traducido '%s' a buscar '%s' en la columna '%s'", nombre_cliente, nombre_a_buscar, columna_a_buscar)

        # Construir consulta dinámica
        query = "SELECT * FROM previo WHERE "
        params = []
        conditions = []
        
        if clave:
            conditions.append("clave = %s")
            params.append(clave)

        # Usamos la columna y el nombre correctos para la búsqueda
        if nombre_a_buscar:
            # Usamos f-string para insertar el nombre de la columna dinámicamente
            conditions.append(f"{columna_a_buscar} LIKE %s")
            params.append(f"%{nombre_a_buscar}%")
        
        query += " AND ".join(conditions)
        
        cursor.execute(query, tuple(params))
        resultados = cursor.fetchall()

        if not resultados:
            return jsonify({'error': 'No se encontraron registros'}), 404

        # Convertir Decimal a float
        for fila in resultados:
            for key, value in fila.items():
                if isinstance(value, Decimal):
                    fila[key] = float(value)
        
        return jsonify(resultados), 200

    except Exception as e:
        logging.exception("Error en buscar_caratula_evac")
        return jsonify({'error': 'Error al procesar la solicitud'}), 500
        
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conexion' in locals() and conexion.is_connected():
            conexion.close()

@caratulas_bp.route('/nombres_caratula', methods=['GET'])
def obtener_nombres():
    try:
        # Conexión a BD
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)

        # Consulta directa
        query = """
        SELECT clave, nombre_cliente
        FROM previo
        """
        cursor.execute(query)
        resultados = cursor.fetchall()

        if not resultados:
            return jsonify({'error': 'No se encontraron registros'}), 404

        return jsonify(resultados), 200

    except Exception as e:
        logging.exception("Error en obtener_nombres")
        return jsonify({'error': 'Error al procesar la solicitud'}), 500

    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@caratulas_bp.route('/clientes_a', methods=['GET'])
def obtener_previo_evac_a():
    try:
        conexion = obtener_conexion()
        with conexion.cursor(dictionary=True) as cursor:
            query = "SELECT * FROM previo WHERE evac = %s"
            cursor.execute(query, ("A",))
            resultados = cursor.fetchall()
        
        # Convertir valores Decimal a float para JSON
        for fila in resultados:
            for key, value in fila.items():
                if isinstance(value, Decimal):
                    fila[key] = float(value)

        return jsonify(resultados), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()
            
@caratulas_bp.route('/clientes_b', methods=['GET'])
def obtener_previo_evac_b():
    try:
        conexion = obtener_conexion()
        with conexion.cursor(dictionary=True) as cursor:
            query = "SELECT * FROM previo WHERE evac = %s"
            cursor.execute(query, ("B",))
            resultados = cursor.fetchall()
        
        # Convertir valores Decimal a float para JSON
        for fila in resultados:
            for key, value in fila.items():
                if isinstance(value, Decimal):
                    fila[key] = float(value)

        return jsonify(resultados), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@caratulas_bp.route('/clientes_go', methods=['GET'])
def obtener_previo_evac_go():
    try:
        conexion = obtener_conexion()
        with conexion.cursor(dictionary=True) as cursor:
            query = "SELECT * FROM previo WHERE evac = %s"
            cursor.execute(query, ("GO",))
            resultados = cursor.fetchall()
        
        # Convertir valores Decimal a float para JSON
        for fila in resultados:
            for key, value in fila.items():
                if isinstance(value, Decimal):
                    fila[key] = float(value)

        return jsonify(resultados), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@caratulas_bp.route('/caratula_evac_a', methods=['POST'])
def actualizar_caratula_evac_a():
    try:
        datos = request.get_json()
        
        # CORRECCIÓN: El frontend envía {datos: [...]} no directamente [...]
        datos_array = datos.get('datos') if isinstance(datos, dict) else datos
        
        if not datos_array or not isinstance(datos_array, list):
            return jsonify({'error': 'Datos no proporcionados correctamente'}), 400
        
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE caratula_evac_a")            
            for i, item in enumerate(datos_array):
                cursor.execute("""
                    INSERT INTO caratula_evac_a 
                    (categoria, meta, acumulado_real, avance_proyectado, porcentaje)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    item.get('categoria'),
                    item.get('meta', 0),
                    item.get('acumulado_real', 0),
                    item.get('avance_proyectado', 0),
                    item.get('porcentaje', 0)
                ))
            
            conexion.commit()
            return jsonify({'success': True, 'message': 'Datos actualizados'}), 200
            
    except Exception as e:
        if 'conexion' in locals():
            conexion.rollback()
            logging.exception("Error en actualizar_caratula_evac_a")
        return jsonify({'error': str(e)}), 500
    
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@caratulas_bp.route('/caratula_evac_b', methods=['POST'])
def actualizar_caratula_evac_b():
    try:
        datos = request.get_json()
        
        # CORRECCIÓN: El frontend envía {datos: [...]} no directamente [...]
        datos_array = datos.get('datos') if isinstance(datos, dict) else datos
        
        if not datos_array or not isinstance(datos_array, list):
            return jsonify({'error': 'Datos no proporcionados correctamente'}), 400
        
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE caratula_evac_b")            
            for i, item in enumerate(datos_array):
                cursor.execute("""
                    INSERT INTO caratula_evac_b
                    (categoria, meta, acumulado_real, avance_proyectado, porcentaje)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    item.get('categoria'),
                    item.get('meta', 0),
                    item.get('acumulado_real', 0),
                    item.get('avance_proyectado', 0),
                    item.get('porcentaje', 0)
                ))
            
            conexion.commit()
            return jsonify({'success': True, 'message': 'Datos actualizados'}), 200
            
    except Exception as e:
        if 'conexion' in locals():
            conexion.rollback()
        logging.exception("Error en actualizar_caratula_evac_b")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@caratulas_bp.route('/datos_evac_a', methods=['GET'])
def obtener_caratula_evac_a():
        try:
            conexion = obtener_conexion()
            with conexion.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM caratula_evac_a")
                resultados = cursor.fetchall()
                # Convertir Decimal a float si es necesario
                for fila in resultados:
                    for key, value in fila.items():
                        if isinstance(value, Decimal):
                            fila[key] = float(value)
            return jsonify(resultados), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if cursor:
                cursor.close()
            if conexion and conexion.is_connected():
                conexion.close()

@caratulas_bp.route('/datos_evac_b', methods=['GET'])
def obtener_caratula_evac_b():
        try:
            conexion = obtener_conexion()
            with conexion.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM caratula_evac_b")
                resultados = cursor.fetchall()
                # Convertir Decimal a float si es necesario
                for fila in resultados:
                    for key, value in fila.items():
                        if isinstance(value, Decimal):
                            fila[key] = float(value)
            return jsonify(resultados), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if cursor:
                cursor.close()
            if conexion and conexion.is_connected():
                conexion.close()

@caratulas_bp.route('/datos_previo', methods=['GET'])
def obtener_datos_previo():
    try:
        conexion = obtener_conexion()
        with conexion.cursor(dictionary=True) as cursor:
            # Excluir las claves dadas
            cursor.execute("""
                SELECT * 
                FROM previo
                WHERE clave NOT IN (
                    'JC539','EC216','LC657',
                    'GC411','MC679','MC677',
                    'LC625','LC626','LC627',
                    'LD653','MD680','ID492',
                    'LD660','NA718','7C042'
                )
            """)
            resultados = cursor.fetchall()
            
            # Convertir Decimal a float si es necesario
            for fila in resultados:
                for key, value in fila.items():
                    if isinstance(value, Decimal):
                        fila[key] = float(value)
                        
        return jsonify(resultados), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@caratulas_bp.route('/generar-pdf', methods=['POST'])
def generar_caratula_pdf():
    """
    Endpoint para generar un PDF de la carátula en el servidor y devolverlo.
    """
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    
    try:
        # 1. Obtener los datos del cliente enviados desde Angular
        data = request.get_json()
        if not data or 'datos_caratula' not in data:
            return jsonify({"error": "No se proporcionaron datos de la carátula"}), 400

        # 2. Reutilizar la lógica para crear el HTML del PDF
        # La función crear_cuerpo_email devuelve un dict con 'html_caratula_pdf'
        htmls = crear_cuerpo_email(data)
        html_para_pdf = htmls['html_caratula_pdf']

        # 3. Generar el PDF en memoria usando WeasyPrint (import dinámico)
        try:
            from weasyprint import HTML
        except Exception as e:
            return jsonify({
                "error": (
                    "WeasyPrint no disponible en el entorno. "
                    "Instale las dependencias del sistema (p.ej. libgobject, pango) "
                    "o ejecute en un entorno donde WeasyPrint esté instalado. Detalle: " + str(e)
                )
            }), 500

        pdf_bytes = HTML(string=html_para_pdf).write_pdf()

        # 4. Preparar el nombre del archivo
        clave_cliente = data.get('datos_caratula', {}).get('clave', 'SIN_CLAVE')
        filename = f"Caratula_{clave_cliente}.pdf"

        # 5. Crear una respuesta de Flask con el contenido del PDF
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )

    except Exception as e:
            logging.exception("Error al generar PDF")
            return jsonify({"error": f"Error interno al generar el PDF: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()
    
@caratulas_bp.route('/verificar_grupo_cliente', methods=['GET'])
def verificar_grupo_cliente():
    """
    Verifica si un cliente, basado en su clave, pertenece a un grupo.
    Si pertenece, devuelve el ID y el nombre del grupo.
    """
    clave = request.args.get('clave')
    if not clave:
        return jsonify({'error': 'Se requiere la clave del cliente'}), 400

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        
        query = """
            SELECT
                c.id_grupo,
                g.nombre_grupo
            FROM clientes c
            JOIN grupo_clientes g ON c.id_grupo = g.id
            WHERE c.clave = %s AND c.id_grupo IS NOT NULL;
        """
        cursor.execute(query, (clave,))
        resultado = cursor.fetchone()

        if resultado:
            # ¡Éxito! El cliente tiene un grupo.
            return jsonify({
                'tiene_grupo': True,
                'id_grupo': resultado['id_grupo'],
                'nombre_grupo': resultado['nombre_grupo']
            })
        else:
            # El cliente no pertenece a ningún grupo.
            return jsonify({'tiene_grupo': False})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conexion' in locals() and conexion.is_connected():
            conexion.close()


@caratulas_bp.route('/debug-odoo', methods=['GET'])
def debug_odoo():
    """Debug helper (dev only): intenta conectarse a Odoo y buscar partners para un cliente dado.
    Devuelve uid y número de partners encontrados o el error.
    """
    cliente = request.args.get('cliente')
    try:
        uid, models = get_odoo_models()
        if not uid or not models:
            return jsonify({'ok': False, 'error': 'No se pudo autenticar en Odoo', 'uid': uid}), 500

        if not cliente:
            return jsonify({'ok': True, 'uid': uid})

        try:
            partners = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'res.partner', 'search_read', [[['name', 'ilike', cliente]]], {'fields': ['id', 'name']})
            return jsonify({'ok': True, 'uid': uid, 'partners_count': len(partners), 'sample': partners[:5]}), 200
        except Exception as ex:
            logging.exception('debug-odoo: error buscando partners')
            return jsonify({'ok': False, 'error': str(ex)}), 500

    except Exception as e:
        logging.exception('debug-odoo: excepción inesperada')
        return jsonify({'ok': False, 'error': str(e)}), 500


@caratulas_bp.route('/detalle-compras-odoo', methods=['GET'])
def detalle_compras_odoo():
    """
    Devuelve el historial completo de órdenes de venta de un cliente desde Odoo.
    - Incluye el estado de la orden (Cotización, Confirmada, Bloqueada, Cancelada).
    - Excluye productos con clave FLE o nombre "Standard delivery".
    - Todos los pickings, moves y move_lines se leen en batch (una sola llamada por modelo)
      para minimizar la latencia.
    """
    cliente = request.args.get('cliente')
    estado_filtro = request.args.get('estado')  # opcional
    # grupo_odoo: Vista Global de integral → consulta DB por claves del grupo, luego Odoo con ref IN
    grupo_odoo = request.args.get('grupo')
    # Cuando ref_exacta=1 la búsqueda es solo por ref exact en res.partner
    # (usado en "Mis Pedidos" de usuarios integrales para evitar matches parciales)
    ref_exacta = request.args.get('ref_exacta') in ('1', 'true', 'True')
    try:
        _limit_raw = request.args.get('limit')
        limit = int(_limit_raw) if _limit_raw is not None else None
        if limit is not None and limit <= 0:
            limit = None  # 0 o negativo → sin límite, devolver todo
    except Exception:
        limit = None
    try:
        offset = int(request.args.get('offset')) if request.args.get('offset') is not None else 0
    except Exception:
        offset = 0

    if not cliente and not grupo_odoo:
        return jsonify({'error': 'Se requiere parámetro cliente o grupo'}), 400

    uid, models, odoo_err = get_odoo_models()
    if not uid or not models:
        logging.error('detalle_compras_odoo: no se pudo conectar a Odoo')
        return jsonify({'error': 'No se pudo conectar a Odoo', 'detail': odoo_err}), 500

    # Etiquetas legibles para el estado de la orden de venta
    SALE_STATE_LABELS = {
        'draft':  'Cotización',
        'sent':   'Cotización Enviada',
        'sale':   'Orden Confirmada',
        'done':   'Bloqueada',
        'cancel': 'Cancelada',
    }

    def map_estado_picking(state):
        if state == 'assigned':
            return 'En inventario'
        if state == 'done':
            return 'Entregado'
        if state == 'waiting':
            return 'Falta de confirmación'
        if state in ('confirmed', 'partially_available'):
            return 'En tránsito'
        if state == 'cancel':
            return 'Cancelado'
        return state or ''

    def es_producto_excluido(prod):
        """True si el producto es FLE, Standard delivery, Descuento o línea sin SKU de ese tipo."""
        if not prod:
            return False
        code = (prod.get('default_code') or '').strip().upper()
        name = (prod.get('name') or '').strip().lower()
        return (
            code.startswith('FLE')
            or 'standard delivery' in name
            or 'descuento' in name
        )

    try:
        # ── 1) Determinar el dominio de partners según el modo de búsqueda ──────────────
        try:
            if grupo_odoo:
                # Vista Global de integral: obtener todas las claves del grupo desde DB
                # y buscar exactamente esos partners en Odoo por ref
                try:
                    _conn = obtener_conexion()
                    _cur = _conn.cursor(dictionary=True)
                    _cur.execute(
                        "SELECT clave FROM clientes WHERE id_grupo = %s AND clave IS NOT NULL AND clave != ''",
                        (grupo_odoo,)
                    )
                    _claves = [r['clave'] for r in _cur.fetchall()]
                    _cur.close()
                    _conn.close()
                except Exception as db_ex:
                    return jsonify({'error': f'Error consultando claves del grupo: {str(db_ex)}'}), 500

                if not _claves:
                    return jsonify({'data': [], 'rows': [], 'meta': {'total': 0}}), 200

                partner_domain = [['ref', 'in', _claves]]
            elif ref_exacta:
                # Modo "Mis Pedidos" de integral: solo match exacto por ref
                # Si la clave no existe en Odoo devuelve lista vacía (modal en blanco)
                partner_domain = [['ref', '=', cliente]]
            else:
                # Modo global/normal: busca por nombre o ref con ilike
                partner_domain = ['|', ['name', 'ilike', cliente], ['ref', 'ilike', cliente]]

            partners = models.execute_kw(
                ODOO_DB, uid, ODOO_PASSWORD,
                'res.partner', 'search_read',
                [partner_domain],
                {'fields': ['id', 'name', 'ref', 'child_ids'], 'limit': 0}
            )
        except Exception as ex:
            return jsonify({'error': f'Error consultando res.partner: {str(ex)}'}), 500

        if not partners:
            return jsonify({'data': [], 'rows': [], 'meta': {'total': 0}}), 200

        # Para búsqueda por ref exacta (grupo o Mis Pedidos) solo usamos los partners
        # encontrados directamente — NO expandimos child_ids, porque los contactos hijo
        # de una empresa pertenecen a otras empresas o son direcciones de envío y sus
        # órdenes inflarían los resultados incorrectamente.
        # Para búsqueda ilike (usuario normal) sí incluimos hijos porque en ese modo
        # las órdenes pueden estar registradas en contactos hijo de la empresa.
        all_partner_ids = set()
        for p in partners:
            all_partner_ids.add(p['id'])
            if not (grupo_odoo or ref_exacta):
                for child_id in (p.get('child_ids') or []):
                    all_partner_ids.add(child_id)
        partner_ids = list(all_partner_ids)

        # ── 2) Traer órdenes de venta desde 2025-07-01 (incluyendo campo state) ────────
        try:
            orders = models.execute_kw(
                ODOO_DB, uid, ODOO_PASSWORD,
                'sale.order', 'search_read',
                [[['partner_id', 'in', partner_ids], ['date_order', '>=', '2025-07-01']]],
                {'fields': ['id', 'name', 'date_order', 'partner_id', 'order_line', 'amount_total', 'state'],
                 'order': 'date_order desc', 'limit': 0}
            )
        except Exception as ex:
            return jsonify({'error': f'Error consultando sale.order: {str(ex)}'}), 500

        if not orders:
            return jsonify({'data': [], 'rows': [], 'meta': {'total': 0}}), 200

        # ── 3) Leer líneas en batch ───────────────────────────────────────────────
        all_line_ids = []
        for o in orders:
            all_line_ids.extend(o.get('order_line') or [])

        lines_map = {}
        if all_line_ids:
            try:
                all_lines = models.execute_kw(
                    ODOO_DB, uid, ODOO_PASSWORD,
                    'sale.order.line', 'search_read',
                    [[['id', 'in', all_line_ids]]],
                    {'fields': ['id', 'order_id', 'product_id', 'name', 'product_uom_qty', 'qty_delivered', 'price_unit'], 'limit': 0}
                )
                for l in all_lines:
                    lines_map[l['id']] = l
            except Exception:
                pass

        # ── 4) Leer productos en batch (excluir FLE / Standard delivery) ─────────
        product_ids = set()
        for l in lines_map.values():
            pid = l.get('product_id') and l['product_id'][0]
            if pid:
                product_ids.add(pid)

        products_map = {}
        if product_ids:
            try:
                prods = models.execute_kw(
                    ODOO_DB, uid, ODOO_PASSWORD,
                    'product.product', 'search_read',
                    [[['id', 'in', list(product_ids)]]],
                    {'fields': ['id', 'default_code', 'name'], 'limit': 0}
                )
                for p in prods:
                    products_map[p['id']] = p
            except Exception:
                pass

        # ── 5) Leer facturas en batch ─────────────────────────────────────────────
        order_names = [o['name'] for o in orders if o.get('name')]
        invoices_map_by_origin = {}
        try:
            inv_rows = models.execute_kw(
                ODOO_DB, uid, ODOO_PASSWORD,
                'account.move', 'search_read',
                [[['origin', 'in', order_names], ['move_type', '=', 'out_invoice']]],
                {'fields': ['id', 'name', 'invoice_date', 'origin'], 'limit': 0}
            )
            for m in inv_rows:
                invoices_map_by_origin.setdefault(m.get('origin'), []).append(m)
        except Exception:
            pass

        # ── 6) Determinar campos disponibles en stock.* UNA SOLA VEZ ─────────────
        picking_keys = set()
        try:
            pf = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'stock.picking', 'fields_get', [], {})
            picking_keys = set(pf.keys()) if isinstance(pf, dict) else set()
        except Exception:
            pass

        move_keys = set()
        try:
            mf = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'stock.move', 'fields_get', [], {})
            move_keys = set(mf.keys()) if isinstance(mf, dict) else set()
        except Exception:
            pass

        mline_keys = set()
        try:
            mlf = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'stock.move.line', 'fields_get', [], {})
            mline_keys = set(mlf.keys()) if isinstance(mlf, dict) else set()
        except Exception:
            pass

        # ── 7) Leer TODOS los pickings en un solo batch ───────────────────────────
        picking_want_fields = ['name', 'state', 'picking_type_id', 'picking_type_code', 'scheduled_date', 'origin']
        if 'move_ids' in picking_keys:
            picking_want_fields.append('move_ids')
        if 'move_line_ids' in picking_keys:
            picking_want_fields.append('move_line_ids')

        all_pickings = []
        try:
            all_pickings = models.execute_kw(
                ODOO_DB, uid, ODOO_PASSWORD,
                'stock.picking', 'search_read',
                [[['origin', 'in', order_names]]],
                {'fields': picking_want_fields, 'limit': 0}
            )
        except Exception:
            pass

        pickings_by_origin = {}
        for p in all_pickings:
            pickings_by_origin.setdefault(p.get('origin'), []).append(p)

        # ── 8) Leer TODOS los stock.move en un solo batch ─────────────────────────
        all_move_ids = []
        for p in all_pickings:
            all_move_ids.extend(p.get('move_ids') or [])

        m_fields = ['product_id', 'product_uom_qty', 'state', 'picking_id']
        if 'quantity_done' in move_keys:
            m_fields.append('quantity_done')
        elif 'qty_done' in move_keys:
            m_fields.append('qty_done')

        moves_by_picking = {}
        if all_move_ids:
            try:
                move_rows = models.execute_kw(
                    ODOO_DB, uid, ODOO_PASSWORD,
                    'stock.move', 'search_read',
                    [[['id', 'in', all_move_ids]]],
                    {'fields': m_fields, 'limit': 0}
                )
                for m in move_rows:
                    p_id = m.get('picking_id') and m['picking_id'][0]
                    if p_id:
                        moves_by_picking.setdefault(p_id, []).append(m)
            except Exception:
                pass

        # ── 9) Leer TODOS los stock.move.line en un solo batch ───────────────────
        all_mline_ids = []
        for p in all_pickings:
            all_mline_ids.extend(p.get('move_line_ids') or [])

        ml_fields = ['product_id', 'product_uom_qty', 'state', 'picking_id']
        if 'qty_done' in mline_keys:
            ml_fields.append('qty_done')
        elif 'quantity_done' in mline_keys:
            ml_fields.append('quantity_done')

        mlines_by_picking = {}
        if all_mline_ids:
            try:
                ml_rows = models.execute_kw(
                    ODOO_DB, uid, ODOO_PASSWORD,
                    'stock.move.line', 'search_read',
                    [[['id', 'in', all_mline_ids]]],
                    {'fields': ml_fields, 'limit': 0}
                )
                for ml in ml_rows:
                    p_id = ml.get('picking_id') and ml['picking_id'][0]
                    if p_id:
                        mlines_by_picking.setdefault(p_id, []).append(ml)
            except Exception:
                pass

        # ── 10) Mapa de entrega por (orden, product_id) ─────────────────────────
        # Solo tomamos pickings OUTGOING (entrega al cliente) para no confundir
        # movimientos internos (Pick→Ship multi-paso) con la entrega real.
        entrega_por_prod = {}
        for p in all_pickings:
            # Filtrar solo pickings de salida (entrega al cliente)
            ptype = p.get('picking_type_code') or ''
            if ptype and ptype != 'outgoing':
                continue
            origin = p.get('origin') or ''
            p_id = p['id']
            for m in (moves_by_picking.get(p_id) or []):
                prod_id = m.get('product_id') and m['product_id'][0]
                if not prod_id or not origin:
                    continue
                key = (origin, prod_id)
                if key not in entrega_por_prod:
                    entrega_por_prod[key] = {'qty': 0.0, 'done': 0.0, 'estados': set()}
                entrega_por_prod[key]['qty']  += float(m.get('product_uom_qty') or 0)
                done_qty = m.get('quantity_done') or m.get('qty_done') or 0
                entrega_por_prod[key]['done'] += float(done_qty)
                raw_state = m.get('state') or ''
                if raw_state:
                    entrega_por_prod[key]['estados'].add(raw_state)

        def estatus_por_producto(order_name: str, product_id) -> str | None:
            """Devuelve el estatus de entrega de un producto específico en una orden."""
            info = entrega_por_prod.get((order_name, product_id))
            if not info or not info['estados']:
                return None
            estados = info['estados']
            qty   = info['qty']
            done  = info['done']
            # Prioridad: Entregado > Entregado Parcial > En inventario > Falta de confirmación > En tránsito > Cancelado
            if 'done' in estados:
                if qty > 0 and done >= qty:
                    return 'Entregado'
                elif done > 0:
                    return 'Entregado Parcial'
                return 'Entregado'
            if 'assigned' in estados:
                return 'En inventario'
            if 'waiting' in estados:
                return 'Falta de confirmación'
            if estados & {'confirmed', 'partially_available'}:
                return 'En tránsito'
            if 'cancel' in estados:
                return 'Cancelado'
            return map_estado_picking(next(iter(estados)))

        # ── 11) Construir resultado ───────────────────────────────────────────────
        resultado = []
        filas_planas = []

        for o in orders:
            estado_orden_raw = o.get('state') or ''
            estado_orden = SALE_STATE_LABELS.get(estado_orden_raw, estado_orden_raw)

            order_obj = {
                'orden': o.get('name'),
                'fecha': o.get('date_order'),
                'cliente': o['partner_id'][1] if o.get('partner_id') else None,
                'monto_total': float(o.get('amount_total') or 0),
                'estado_orden': estado_orden,
                'estado_orden_raw': estado_orden_raw,
                'lineas': [],
                'pickings': []
            }

            # Líneas — filtrando FLE / Standard delivery
            for lid in (o.get('order_line') or []):
                l = lines_map.get(lid)
                if not l:
                    continue
                pid = l.get('product_id') and l['product_id'][0]
                prod = products_map.get(pid) if pid else None
                if es_producto_excluido(prod):
                    continue
                clave = prod.get('default_code') if prod else None
                producto_nombre = prod.get('name') if prod else (l['product_id'][1] if l.get('product_id') else None)
                cantidad = float(l.get('product_uom_qty') or 0)
                precio = float(l.get('price_unit') or 0)
                order_obj['lineas'].append({
                    'id': l['id'],
                    'product_id_odoo': pid,   # guardamos el ID para cruzar con moves
                    'producto': producto_nombre,
                    'clave_producto': clave,
                    'descripcion': l.get('name'),
                    'cantidad_pedida': cantidad,
                    'cantidad_entregada': float(l.get('qty_delivered') or 0),
                    'precio_unitario': precio,
                    'total_linea': round(cantidad * precio, 2)
                })

            # Pickings (todos leídos en batch, solo se indexan aquí)
            for p in (pickings_by_origin.get(o.get('name')) or []):
                estado_mapeado = map_estado_picking(p.get('state'))
                ptype_code = p.get('picking_type_code') or ''
                p_id = p['id']
                moves_result = []

                for m in (moves_by_picking.get(p_id) or []):
                    cantidad_hecha = m.get('quantity_done') or m.get('qty_done') or 0
                    moves_result.append({
                        'producto': m['product_id'][1] if m.get('product_id') else None,
                        'cantidad': float(m.get('product_uom_qty') or 0),
                        'cantidad_hecha': float(cantidad_hecha),
                        'state': m.get('state')
                    })

                for ml in (mlines_by_picking.get(p_id) or []):
                    cantidad_hecha_ml = ml.get('qty_done') or ml.get('quantity_done') or 0
                    moves_result.append({
                        'producto': ml['product_id'][1] if ml.get('product_id') else None,
                        'cantidad': float(ml.get('product_uom_qty') or 0),
                        'cantidad_hecha': float(cantidad_hecha_ml),
                        'state': ml.get('state')
                    })

                order_obj['pickings'].append({
                    'picking': p.get('name'),
                    'estado': estado_mapeado,
                    'picking_type_code': ptype_code,
                    'scheduled_date': p.get('scheduled_date'),
                    'moves': moves_result
                })

            # Filas planas para la tabla del frontend
            facturas_rel = invoices_map_by_origin.get(o.get('name'), [])
            factura_nombre = facturas_rel[0]['name'] if facturas_rel else None
            fecha_factura = facturas_rel[0].get('invoice_date') if facturas_rel else None
            order_name = o.get('name')

            for lin in order_obj['lineas']:
                # Estatus individual por producto cruzando con los moves de los pickings
                estatus_out_lin = estatus_por_producto(order_name, lin.get('product_id_odoo'))
                # Fallback: si no hay moves en pickings outgoing, usar el primer picking outgoing de la orden
                if estatus_out_lin is None:
                    pickings_out = [p for p in order_obj['pickings'] if (p.get('picking_type_code') or '') == 'outgoing']
                    if pickings_out:
                        estatus_out_lin = pickings_out[0]['estado']
                    elif order_obj['pickings']:
                        estatus_out_lin = order_obj['pickings'][0]['estado']
                filas_planas.append({
                    'numero_factura': factura_nombre or order_name,
                    'clave_producto': lin.get('clave_producto'),
                    'producto': lin.get('producto'),
                    'descripcion': lin.get('descripcion'),
                    'fecha': fecha_factura or o.get('date_order'),
                    'precio_unitario': lin.get('precio_unitario'),
                    'cantidad': lin.get('cantidad_pedida'),
                    'cantidad_entregada': lin.get('cantidad_entregada', 0),
                    'total': lin.get('total_linea'),
                    'orden': order_name,
                    'estado_orden': estado_orden,
                    'estado_orden_raw': estado_orden_raw,
                    'cliente': order_obj['cliente'],
                    'pickings': order_obj['pickings'],
                    'estatus_out': estatus_out_lin
                })

            resultado.append(order_obj)

        # Filtro opcional por estado de picking
        if estado_filtro:
            filas_planas = [f for f in filas_planas if f.get('estatus_out') == estado_filtro]

        total = len(filas_planas)
        filas_pag = filas_planas[offset: offset + limit] if limit is not None else filas_planas[offset:]

        return jsonify({
            'data': resultado,
            'rows': filas_pag,
            'meta': {'total': total, 'limit': limit, 'offset': offset, 'returned': len(filas_pag)}
        }), 200

    except Exception as e:
        tb = traceback.format_exc()
        logging.exception('detalle_compras_odoo: excepción inesperada')
        return jsonify({'error': str(e), 'trace': tb}), 500