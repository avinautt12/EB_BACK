from flask import Blueprint, jsonify
from db_conexion import obtener_conexion
import decimal
import traceback
from datetime import date, datetime
from utils.odoo_utils import get_odoo_models, ODOO_DB, ODOO_PASSWORD 

retroactivos_bp = Blueprint('retroactivos', __name__, url_prefix='')

# ==============================================================================
# 1. FUNCIÓN MAESTRA: OBTENER DEDUCCIONES (MOTOR BLINDADO)
# ==============================================================================
def obtener_deducciones_odoo(claves_db):
    resultado_odoo = get_odoo_models()
    uid = resultado_odoo[0]     # Tomamos el primer valor (UID)
    models = resultado_odoo[1]
    if not uid: return {}

    # FECHAS OFICIALES DE TEMPORADA MY26
    fecha_inicio = '2025-07-01'
    fecha_fin = '2026-06-30'
    
    print("🔎 Mapeando IDs internos de Odoo con las Claves de la Base de Datos...")
    partners_odoo = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'res.partner', 'search_read',
        [[]], {'fields': ['id', 'name', 'ref']})

    odoo_id_to_clave = {}
    
    for p in partners_odoo:
        ref_odoo = str(p.get('ref', '')).strip().upper()
        name_odoo = str(p.get('name', '')).strip().upper()

        for clave in claves_db:
            if clave == ref_odoo or clave in name_odoo:
                odoo_id_to_clave[p['id']] = clave
                break

    redirecciones = {
        'VICTOR HUGO VILLANUEVA GUZMAN': 'LC657',
        'MARCO TULIO ANDRADE NAVARRO': 'JC539',
        'NARUCO': 'LC625'
    }
    for p in partners_odoo:
        name_odoo = str(p.get('name', '')).strip().upper()
        if p['id'] not in odoo_id_to_clave and name_odoo in redirecciones:
            odoo_id_to_clave[p['id']] = redirecciones[name_odoo]

    resultados_por_clave = {clave: {'nc': 0.0, 'garantia': 0.0, 'ofertado': 0.0} for clave in claves_db}

    def agregar_valor(partner_id_odoo, tipo, valor):
        clave_encontrada = odoo_id_to_clave.get(partner_id_odoo)
        if clave_encontrada and clave_encontrada in resultados_por_clave:
            resultados_por_clave[clave_encontrada][tipo] += valor

    lista_ids_validos = list(odoo_id_to_clave.keys())
    if not lista_ids_validos:
        return resultados_por_clave

    try:
        # A. GARANTÍAS 
        domain_garantia = [
            ('move_id.move_type', '=', 'out_refund'),
            ('move_id.state', '=', 'posted'),
            ('move_id.invoice_date', '>=', fecha_inicio),
            ('move_id.invoice_date', '<=', fecha_fin),
            ('quantity', '=', 1),
            ('partner_id', 'in', lista_ids_validos),
            '|', ('product_id.default_code', 'ilike', 'DESCGARANTIA'),
                 ('name', 'ilike', 'DESCGARANTIA')
        ]
        lineas_garantia = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read', 
            [domain_garantia], {'fields': ['partner_id', 'price_subtotal', 'name']})
        
        for linea in lineas_garantia:
            if linea['partner_id']:
                agregar_valor(linea['partner_id'][0], 'garantia', float(linea['price_subtotal']))

        # B. PRODUCTOS OFERTADOS 
        domain_ofertado = [
            ('move_id.move_type', '=', 'out_invoice'), 
            ('move_id.state', '=', 'posted'),
            ('move_id.invoice_date', '>=', fecha_inicio),
            ('move_id.invoice_date', '<=', fecha_fin),
            ('quantity', '!=', 0),
            ('partner_id', 'in', lista_ids_validos),
            ('product_id.product_tmpl_id.product_tag_ids.name', 'ilike', 'Producto Ofertado') 
        ]
        lineas_ofertado = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read', 
            [domain_ofertado], {'fields': ['partner_id', 'price_subtotal']})

        for linea in lineas_ofertado:
            if linea['partner_id']:
                agregar_valor(linea['partner_id'][0], 'ofertado', float(linea['price_subtotal']))

        # C. NOTAS DE CRÉDITO 
        domain_nc = [
            ('move_id.move_type', '=', 'out_refund'),
            ('move_id.state', '=', 'posted'),
            ('move_id.invoice_date', '>=', fecha_inicio),
            ('move_id.invoice_date', '<=', fecha_fin),
            ('move_id.l10n_mx_edi_usage', '=', 'G02'),
            ('partner_id', 'in', lista_ids_validos), 
            ('quantity', '=', 1)
        ]
        lineas_nc = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read', 
            [domain_nc], {'fields': ['partner_id', 'price_subtotal', 'name']})

        for linea in lineas_nc:
            if not linea['partner_id']: continue
            monto = float(linea['price_subtotal'])
            nombre_producto = str(linea['name'] or '').upper()
            
            es_garantia = 'GARANTIA' in nombre_producto or 'DESCGARANTIA' in nombre_producto
            es_aplant = 'APLANT' in nombre_producto or 'ANTICIPO' in nombre_producto
            
            es_descuento_valido = 'DESC' in nombre_producto or 'DESCESPECIAL' in nombre_producto or 'DESCPAGO' in nombre_producto
            
            if not es_garantia and not es_aplant and es_descuento_valido:
                agregar_valor(linea['partner_id'][0], 'nc', monto)

        return resultados_por_clave

    except Exception as e:
        print(f"❌ Error Odoo: {e}")
        traceback.print_exc()
        return {}
    
# ==============================================================================
# 2. ENDPOINT GET GLOBALES (Con matemáticas en Python)
# ==============================================================================
@retroactivos_bp.route('/retroactivos', methods=['GET'])
def obtener_retroactivos():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT 
                id, id_previo, CLAVE, ZONA, CLIENTE, CATEGORIA,
                COMPRA_MINIMA_ANUAL, COMPRA_MINIMA_APPAREL,
                COMPRAS_TOTALES_CRUDO, META_MY26_CUMPLIDA,
                COMPRA_GLOBAL_SCOTT, COMPRA_GLOBAL_APPAREL, COMPRA_GLOBAL_BOLD,
                TOTAL_ACUMULADO, compra_anual_crudo, compra_adicional,
                notas_credito, garantias, productos_ofertados,
                bicicleta_demo, bicicletas_bold, importe_final,
                porcentaje_retroactivo, porcentaje_retroactivo_apparel,
                retroactivo_total, importe, estatus, fecha_aplicacion, NC, FACT
            FROM tabla_retroactivos
            WHERE COALESCE(CATEGORIA, '') != 'Distribuidor'
            ORDER BY CASE WHEN ZONA = 'A' THEN 1 WHEN ZONA = 'B' THEN 2 WHEN ZONA = 'GO' THEN 3 ELSE 4 END, CLIENTE ASC
        """)
        resultados = cursor.fetchall()

        for fila in resultados:
            for clave, valor in fila.items():
                if isinstance(valor, decimal.Decimal):
                    fila[clave] = float(valor)
                elif isinstance(valor, (datetime, date)):
                    fila[clave] = valor.strftime('%Y-%m-%d')
            
            # --- MATEMÁTICAS TRASLADADAS DESDE ANGULAR HACIA PYTHON ---
            m_anual = fila.get('COMPRA_MINIMA_ANUAL', 0)
            m_apparel = fila.get('COMPRA_MINIMA_APPAREL', 0)
            
            fila['porcentaje_avance_general'] = (fila.get('COMPRAS_TOTALES_CRUDO', 0) / m_anual) if m_anual > 0 else 0.0
            fila['porcentaje_avance_scott'] = (fila.get('COMPRA_GLOBAL_SCOTT', 0) / m_anual) if m_anual > 0 else 0.0
            fila['porcentaje_avance_apparel'] = (fila.get('COMPRA_GLOBAL_APPAREL', 0) / m_apparel) if m_apparel > 0 else 0.0
            
            fila['total_bicis_deduccion'] = fila.get('bicicleta_demo', 0) + fila.get('bicicletas_bold', 0)
            fila['acumulado_global_calculado'] = fila.get('COMPRAS_TOTALES_CRUDO', 0) - fila.get('notas_credito', 0) - fila.get('garantias', 0)
        
        return jsonify(resultados), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conexion: conexion.close()

# ==============================================================================
# 3. ENDPOINT POST (Sincronización Completa + CÁLCULO NUEVO MY26 + INTEGRALES)
# ==============================================================================
@retroactivos_bp.route('/sincronizar_notas', methods=['POST'])
def sincronizar_notas_odoo():
    # [AQUÍ VA EXACTAMENTE EL MISMO CÓDIGO DEL POST QUE YA TIENES]
    conexion = obtener_conexion()
    cursor_dict = conexion.cursor(dictionary=True)
    cursor = conexion.cursor() 
    try:
        print("🔵 Iniciando sincronización...")
        cursor_dict.execute("SELECT CLAVE FROM tabla_retroactivos WHERE CLAVE NOT LIKE 'Integral%'")
        claves_db = [row['CLAVE'].strip().upper() for row in cursor_dict.fetchall() if row['CLAVE']]

        datos_por_clave = obtener_deducciones_odoo(claves_db)
        
        cursor.execute("UPDATE tabla_retroactivos SET notas_credito=0, garantias=0, productos_ofertados=0, NC='', FACT='', estatus='Pendiente'")

        for clave, valores in datos_por_clave.items():
            if valores['nc'] != 0 or valores['garantia'] != 0 or valores['ofertado'] != 0:
                cursor.execute("""
                    UPDATE tabla_retroactivos 
                    SET notas_credito = %s, garantias = %s, productos_ofertados = %s WHERE CLAVE = %s
                """, (valores['nc'], valores['garantia'], valores['ofertado'], clave))

        integrales_map = {
            'Integral 1': ['EC216', 'JC539'],
            'Integral 2': ['GC411', 'MC679', 'MC677', 'LC657'],
            'Integral 3': ['LC625', 'LC627', 'LC626']
        }
        
        for clave_padre, claves_hijas in integrales_map.items():
            format_strings = ','.join(['%s'] * len(claves_hijas))
            query_suma = f"SELECT COALESCE(SUM(notas_credito), 0), COALESCE(SUM(garantias), 0), COALESCE(SUM(productos_ofertados), 0) FROM tabla_retroactivos WHERE CLAVE IN ({format_strings})"
            cursor.execute(query_suma, tuple(claves_hijas))
            suma = cursor.fetchone()
            if suma:
                cursor.execute("UPDATE tabla_retroactivos SET notas_credito = %s, garantias = %s, productos_ofertados = %s WHERE CLAVE = %s", (suma[0], suma[1], suma[2], clave_padre))

        cursor.execute("""
            UPDATE tabla_retroactivos
            SET 
                COMPRAS_TOTALES_CRUDO = (COALESCE(COMPRA_GLOBAL_SCOTT, 0) + COALESCE(COMPRA_GLOBAL_APPAREL, 0) + COALESCE(COMPRA_GLOBAL_BOLD, 0)),
                TOTAL_ACUMULADO = (COALESCE(COMPRA_GLOBAL_SCOTT, 0) + COALESCE(COMPRA_GLOBAL_APPAREL, 0) + COALESCE(COMPRA_GLOBAL_BOLD, 0)),
                compra_anual_crudo = ((COALESCE(COMPRA_GLOBAL_SCOTT, 0) + COALESCE(COMPRA_GLOBAL_APPAREL, 0) + COALESCE(COMPRA_GLOBAL_BOLD, 0)) - COALESCE(notas_credito, 0) - COALESCE(productos_ofertados, 0)),
                compra_adicional = (((COALESCE(COMPRA_GLOBAL_SCOTT, 0) + COALESCE(COMPRA_GLOBAL_APPAREL, 0) + COALESCE(COMPRA_GLOBAL_BOLD, 0)) - COALESCE(notas_credito, 0) - COALESCE(productos_ofertados, 0)) - COALESCE(COMPRA_MINIMA_ANUAL, 0))
        """)
        
        cursor.execute("""
            UPDATE tabla_retroactivos
            SET 
                porcentaje_retroactivo = CASE
                    WHEN compra_adicional >= 5000000 THEN 0.045
                    WHEN compra_adicional >= 2000000 THEN 0.02
                    WHEN compra_adicional >= 800000 THEN 0.01
                    ELSE 0.00
                END,
                porcentaje_retroactivo_apparel = CASE
                    WHEN COALESCE(COMPRA_GLOBAL_APPAREL, 0) >= COALESCE(COMPRA_MINIMA_APPAREL, 0) AND COALESCE(COMPRA_MINIMA_APPAREL, 0) > 0 THEN
                        CASE WHEN CATEGORIA LIKE '%Partner Elite%' THEN 0.025 WHEN CATEGORIA = 'Partner' THEN 0.015 ELSE 0.00 END
                    ELSE 0.00
                END
        """)

        cursor.execute("""
            UPDATE tabla_retroactivos
            SET
                retroactivo_total = (COALESCE(porcentaje_retroactivo, 0) + COALESCE(porcentaje_retroactivo_apparel, 0)),
                importe = (COALESCE(importe_final, 0) * (COALESCE(porcentaje_retroactivo, 0) + COALESCE(porcentaje_retroactivo_apparel, 0)))
        """)

        conexion.commit()
        return jsonify({"mensaje": "Sincronización exitosa"}), 200

    except Exception as e:
        if conexion: conexion.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor_dict: cursor_dict.close()
        if cursor: cursor.close()
        if conexion: conexion.close()

# ==============================================================================
# 4. ENDPOINT GET INDIVIDUAL (Con matemáticas en Python)
# ==============================================================================
@retroactivos_bp.route('/retroactivo_cliente/<string:identificador>', methods=['GET'])
def obtener_retroactivo_individual(identificador):
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    try:
        query = """
            SELECT 
                CLAVE, ZONA, CLIENTE, CATEGORIA,
                COMPRA_MINIMA_ANUAL, COMPRA_GLOBAL_SCOTT,
                COMPRA_MINIMA_APPAREL, COMPRA_GLOBAL_APPAREL,
                COMPRAS_TOTALES_CRUDO, notas_credito, garantias,
                productos_ofertados, bicicleta_demo, bicicletas_bold,
                importe_final, porcentaje_retroactivo, porcentaje_retroactivo_apparel,
                compra_adicional, retroactivo_total, importe, estatus, NC, FACT
            FROM tabla_retroactivos
            WHERE CLAVE = %s OR CLIENTE = %s
            LIMIT 1
        """
        cursor.execute(query, (identificador, identificador))
        cliente_data = cursor.fetchone()

        if not cliente_data:
            return jsonify({"mensaje": "Cliente no encontrado"}), 404

        for clave, valor in cliente_data.items():
            if isinstance(valor, decimal.Decimal):
                cliente_data[clave] = float(valor)
            elif valor is None:
                cliente_data[clave] = 0.0 if clave not in ['CLAVE','ZONA','CLIENTE','CATEGORIA','estatus','NC','FACT'] else ''

        # --- MATEMÁTICAS TRASLADADAS DESDE ANGULAR HACIA PYTHON ---
        minima_anual = cliente_data['COMPRA_MINIMA_ANUAL']
        minima_apparel = cliente_data['COMPRA_MINIMA_APPAREL']
        
        cliente_data['porcentaje_avance_general'] = (cliente_data['COMPRAS_TOTALES_CRUDO'] / minima_anual) if minima_anual > 0 else 0.0
        cliente_data['porcentaje_avance_scott'] = (cliente_data['COMPRA_GLOBAL_SCOTT'] / minima_anual) if minima_anual > 0 else 0.0
        cliente_data['porcentaje_avance_apparel'] = (cliente_data['COMPRA_GLOBAL_APPAREL'] / minima_apparel) if minima_apparel > 0 else 0.0
        
        cliente_data['total_bicis_deduccion'] = cliente_data['bicicleta_demo'] + cliente_data['bicicletas_bold']
        cliente_data['acumulado_global_calculado'] = cliente_data['COMPRAS_TOTALES_CRUDO'] - cliente_data['notas_credito'] - cliente_data['garantias']

        return jsonify(cliente_data), 200

    except Exception as e:
        print("Error al obtener cliente:", str(e))
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conexion: conexion.close()