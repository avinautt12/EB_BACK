from flask import Blueprint, jsonify, request
from db_conexion import obtener_conexion
from decimal import Decimal
from datetime import date, datetime
from collections import defaultdict
import calendar

# Importamos utilidades (Asegúrate de que existan y funcionen)
from utils.jwt_utils import registrar_auditoria, verificar_token

try:
    from utils.odoo_utils import obtener_saldo_cuenta_odoo
except ImportError:
    # Fallback por si la ruta de importación cambia
    from utils.odoo_utils import obtener_saldo_cuenta_odoo

dashboard_flujo_bp = Blueprint('dashboard_flujo_bp', __name__, url_prefix='/flujo')

# ==============================================================================
# 1. LECTURA: TABLERO MENSUAL
# ==============================================================================
@dashboard_flujo_bp.route('/tablero-mensual', methods=['GET'])
def obtener_tablero_mensual():
    conexion = None
    try:
        fecha_reporte = request.args.get('fecha', '2026-01-01') 
        
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        
        sql = """
            SELECT 
                c.id_concepto,
                c.nombre_concepto,
                c.categoria,
                c.orden_reporte,
                COALESCE(v.monto_proyectado, 0) as proyectado,
                COALESCE(v.monto_real, 0) as real_val
            FROM cat_conceptos c
            LEFT JOIN flujo_valores v 
                ON c.id_concepto = v.id_concepto 
                AND v.fecha_reporte = %s
            ORDER BY c.orden_reporte ASC
        """
        
        cursor.execute(sql, (fecha_reporte,))
        registros = cursor.fetchall()
        
        data_final = []
        
        for row in registros:
            proyectado = float(row['proyectado']) if isinstance(row['proyectado'], Decimal) else float(row['proyectado'])
            real_val = float(row['real_val']) if isinstance(row['real_val'], Decimal) else float(row['real_val'])
            diferencia = real_val - proyectado
            
            data_final.append({
                "id": row['id_concepto'],
                "concepto": row['nombre_concepto'],
                "categoria": row['categoria'],
                "orden": row['orden_reporte'],
                "col_proyectado": proyectado,
                "col_real": real_val,
                "col_diferencia": diferencia,
                "alerta": "negativa" if diferencia < 0 and row['categoria'] == 'Ingresos' else "normal"
            })

        return jsonify({
            "mes_reporte": fecha_reporte,
            "datos": data_final
        }), 200

    except Exception as e:
        print(f"Error en tablero mensual: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conexion:
            cursor.close()
            conexion.close()

# ==============================================================================
# 2. LECTURA: PROYECCIÓN ANUAL
# ==============================================================================
@dashboard_flujo_bp.route('/proyeccion-anual', methods=['GET'])
def obtener_proyeccion_anual():
    conexion = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)

        cursor.execute("SELECT DISTINCT fecha_reporte FROM flujo_valores ORDER BY fecha_reporte ASC")
        fechas_db = cursor.fetchall()
        columnas_fechas = [f['fecha_reporte'].isoformat() for f in fechas_db]

        sql = """
            SELECT 
                c.id_concepto, 
                c.nombre_concepto, 
                c.categoria,
                c.orden_reporte,
                v.fecha_reporte,
                v.monto_proyectado,
                v.monto_real
            FROM cat_conceptos c
            LEFT JOIN flujo_valores v ON c.id_concepto = v.id_concepto
            ORDER BY c.orden_reporte ASC, v.fecha_reporte ASC
        """
        cursor.execute(sql)
        data_raw = cursor.fetchall()

        filas_dict = defaultdict(lambda: {'meta': {}, 'valores': {}})
        
        for row in data_raw:
            id_c = row['id_concepto']
            if not filas_dict[id_c]['meta']:
                filas_dict[id_c]['meta'] = {
                    'concepto': row['nombre_concepto'],
                    'categoria': row['categoria'],
                    'orden': row['orden_reporte']
                }
            
            if row['fecha_reporte']:
                fecha_key = row['fecha_reporte'].isoformat()
                p = float(row['monto_proyectado'] or 0)
                r = float(row['monto_real'] or 0)
                
                filas_dict[id_c]['valores'][fecha_key] = {
                    'proyectado': p,
                    'real': r,
                    'diferencia': r - p
                }

        filas_finales = []
        for id_c in sorted(filas_dict.keys(), key=lambda k: filas_dict[k]['meta']['orden']):
            obj = filas_dict[id_c]
            datos_ordenados = []
            for fecha in columnas_fechas:
                val = obj['valores'].get(fecha, {'proyectado': 0.0, 'real': 0.0, 'diferencia': 0.0})
                datos_ordenados.append(val)

            filas_finales.append({
                'concepto': obj['meta']['concepto'],
                'categoria': obj['meta']['categoria'],
                'datos': datos_ordenados 
            })

        return jsonify({
            'columnas': columnas_fechas,
            'filas': filas_finales
        }), 200

    except Exception as e:
        print(f"Error en proyeccion anual: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conexion: conexion.close()

# ==============================================================================
# 3. y 4. ESCRITURA (GUARDAR VALOR / CREAR CONCEPTO)
# ==============================================================================
@dashboard_flujo_bp.route('/guardar-valor', methods=['POST'])
def guardar_valor():
    auth_header = request.headers.get('Authorization')
    token = auth_header.split(" ")[1] if auth_header and " " in auth_header else None
    
    if not token or not verificar_token(token):
        return jsonify({'error': 'Tu sesión ha expirado.'}), 401

    data = request.get_json()
    conexion = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        id_concepto = data['id_concepto']
        fecha = data['fecha']
        monto = data['monto']
        tipo = data.get('tipo', 'real') 

        # 1. Guardar el valor
        actualizar_valor_bd(cursor, id_concepto, fecha, monto, tipo)
        
        # 2. OBTENER EL NOMBRE DEL CONCEPTO (Para que la auditoría sea legible)
        cursor.execute("SELECT nombre_concepto FROM cat_conceptos WHERE id_concepto = %s", (id_concepto,))
        res_nombre = cursor.fetchone()
        
        # Si el cursor es diccionario o tupla, manejamos ambos casos por seguridad
        if res_nombre:
            if isinstance(res_nombre, dict):
                nombre_concepto = res_nombre['nombre_concepto']
            else:
                nombre_concepto = res_nombre[0]
        else:
            nombre_concepto = f"Concepto {id_concepto}"

        # 3. Registrar auditoría con nombre bonito
        desc = f"Editó {nombre_concepto} ({tipo}) a ${monto}"
        registrar_auditoria(cursor, 'EDICION_CELDA', 'flujo_valores', id_concepto, desc)

        # 4. Recalcular Fórmulas
        f_obj = datetime.strptime(fecha, "%Y-%m-%d")
        recalcular_formulas_flujo(conexion, f_obj.year, f_obj.month)

        conexion.commit()
        return jsonify({"mensaje": "Valor actualizado y fórmulas recalculadas"}), 200

    except Exception as e:
        if conexion: conexion.rollback()
        print(f"Error guardar valor: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conexion: conexion.close()

# ==============================================================================
# 5. SINCRONIZACIÓN CON ODOO
# ==============================================================================
@dashboard_flujo_bp.route('/sincronizar-odoo', methods=['POST'])
def sincronizar_odoo():
    auth_header = request.headers.get('Authorization')
    token = auth_header.split(" ")[1] if auth_header and " " in auth_header else None
    
    if not token or not verificar_token(token):
        return jsonify({'error': 'Tu sesión ha expirado.'}), 401

    print("🔵 INICIANDO SINCRONIZACIÓN CON ODOO...")
    data = request.get_json()
    anio = data.get('anio')
    mes = data.get('mes')
    
    if not anio or not mes:
        return jsonify({"mensaje": "Faltan datos de año o mes"}), 400

    ultimo_dia = calendar.monthrange(anio, mes)[1]
    fecha_inicio = f"{anio}-{mes:02d}-01"
    fecha_fin = f"{anio}-{mes:02d}-{ultimo_dia}"
    
    conexion = None
    actualizados = 0
    errores = 0
    
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        
        # 1. Traer conceptos configurados con cuenta Odoo
        cursor.execute("""
            SELECT id_concepto, nombre_concepto, categoria, codigo_cuenta_odoo 
            FROM cat_conceptos 
            WHERE codigo_cuenta_odoo IS NOT NULL AND codigo_cuenta_odoo != ''
        """)
        conceptos_mapeados = cursor.fetchall()
        
        cursor_update = conexion.cursor()
        
        for c in conceptos_mapeados:
            codigo = c['codigo_cuenta_odoo']
            cat_lower = c['categoria'].lower() if c['categoria'] else ''
            
            # Inteligencia: Ingreso vs Egreso
            es_ingreso = True
            if any(x in cat_lower for x in ['egreso', 'gasto', 'costo', 'pasivo', 'proveedor']):
                es_ingreso = False
            
            print(f"   -> Sincronizando '{c['nombre_concepto']}'...")
            
            # Consultar Odoo
            saldo_real = obtener_saldo_cuenta_odoo(codigo, fecha_inicio, fecha_fin, es_ingreso=es_ingreso)
            
            try:
                # Guardar en BD (Usando la función corregida)
                actualizar_valor_bd(cursor_update, c['id_concepto'], fecha_inicio, saldo_real, 'real')
                actualizados += 1
            except Exception as e_sql:
                print(f"❌ Error SQL ID {c['id_concepto']}: {e_sql}")
                errores += 1

        if actualizados > 0:
            desc = f"Sync Odoo {fecha_inicio}: {actualizados} actualizados."
            registrar_auditoria(cursor_update, 'SYNC_ODOO', 'flujo_valores', 0, desc)

        # 2. RECALCULAR FÓRMULAS
        recalcular_formulas_flujo(conexion, anio, mes)

        conexion.commit()
        return jsonify({"mensaje": f"Sincronización finalizada. {actualizados} conceptos actualizados."}), 200

    except Exception as e:
        if conexion: conexion.rollback()
        print(f"❌ Error CRÍTICO Sync: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conexion: conexion.close()

# ==============================================================================
# 6. AUDITORÍA (LECTURA) - ¡ESTA ES LA QUE FALTABA!
# ==============================================================================
@dashboard_flujo_bp.route('/auditoria', methods=['GET'])
def obtener_historial_auditoria():
    conexion = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        
        sql = """
            SELECT 
                id_auditoria,
                id_usuario,
                nombre_usuario,
                accion,
                tabla_afectada,
                descripcion,
                fecha_hora
            FROM auditoria_movimientos
            ORDER BY fecha_hora DESC
            LIMIT 500
        """
        cursor.execute(sql)
        registros = cursor.fetchall()
        
        for row in registros:
            if row['fecha_hora']:
                row['fecha_hora'] = row['fecha_hora'].isoformat()
        
        return jsonify(registros), 200

    except Exception as e:
        print(f"Error auditoria: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conexion: conexion.close()

# ==============================================================================
# LÓGICA DE CÁLCULO DE FÓRMULAS (ACTUALIZADO CON TUS IDs REALES)
# ==============================================================================
def recalcular_formulas_flujo(conexion, anio, mes):
    """
    Realiza las sumas y restas automáticas usando las LISTAS COMPLETAS DE IDs.
    """
    print(f"🧮 Recalculando fórmulas para {mes}/{anio}...")
    cursor = conexion.cursor(dictionary=True)
    
    fecha_actual = f"{anio}-{mes:02d}-01"
    
    # Calcular mes anterior
    if mes == 1:
        mes_anterior = 12
        anio_anterior = anio - 1
    else:
        mes_anterior = mes - 1
        anio_anterior = anio
        
    fecha_anterior = f"{anio_anterior}-{mes_anterior:02d}-01"

    try:
        # 1. Traer valores a memoria
        sql_fetch = "SELECT id_concepto, monto_real, monto_proyectado FROM flujo_valores WHERE fecha_reporte = %s"
        cursor.execute(sql_fetch, (fecha_actual,))
        rows = cursor.fetchall()
        
        valores = defaultdict(lambda: {'real': 0.0, 'proy': 0.0})
        for r in rows:
            valores[r['id_concepto']]['real'] = float(r['monto_real'] or 0)
            valores[r['id_concepto']]['proy'] = float(r['monto_proyectado'] or 0)

        # =============================================================
        # MAPEO DE IDs REALES (¡ACTUALIZADO!)
        # =============================================================
        
        ID_SALDO_INICIAL = 1
        ID_VENTAS = 2
        ID_TOTAL_RECUPERACION = 4
        
        IDS_OTROS_INGRESOS = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
        ID_TOTAL_OTROS_INGRESOS = 18
        
        ID_TOTAL_ENTRADA_EFECTIVO = 19
        
        # --- AQUÍ ESTABA EL ERROR: Faltaban los IDs del 32 al 39 ---
        IDS_SALIDA_PROVEEDORES = [20, 21, 22, 23, 32, 33, 34, 35, 36, 37, 38, 39]
        ID_TOTAL_SALIDA_PROVEEDORES = 40
        # ------------------------------------------------------------
        
        IDS_GASTOS = [24, 25, 26, 27, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50] 
        ID_TOTAL_GASTOS = 51
        
        IDS_PAGO_CREDITOS = [52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62]
        ID_TOTAL_PAGO_CREDITOS = 63
        
        ID_TOTAL_SALIDAS_EFECTIVO = 64
        ID_TOTAL_DISPONIBLE = 66

        # =============================================================
        # CÁLCULOS
        # =============================================================

        # 1. Saldo Inicial (Viene del disponible del mes anterior)
        sql_ant = "SELECT monto_real FROM flujo_valores WHERE id_concepto = %s AND fecha_reporte = %s"
        cursor.execute(sql_ant, (ID_TOTAL_DISPONIBLE, fecha_anterior))
        res_prev = cursor.fetchone()
        
        saldo_inicial = float(res_prev['monto_real']) if res_prev else 0.0
        
        # Si es el primer mes y no hay anterior, respetamos lo que haya puesto el usuario
        if saldo_inicial == 0 and mes == 1 and anio == 2026:
             saldo_inicial = valores[ID_SALDO_INICIAL]['real']

        actualizar_valor_bd(cursor, ID_SALDO_INICIAL, fecha_actual, saldo_inicial, 'real')
        valores[ID_SALDO_INICIAL]['real'] = saldo_inicial 

        # 2. Totales Simples
        actualizar_valor_bd(cursor, ID_TOTAL_RECUPERACION, fecha_actual, valores[ID_VENTAS]['real'], 'real')
        valores[ID_TOTAL_RECUPERACION]['real'] = valores[ID_VENTAS]['real']

        suma_otros = sum(valores[uid]['real'] for uid in IDS_OTROS_INGRESOS)
        actualizar_valor_bd(cursor, ID_TOTAL_OTROS_INGRESOS, fecha_actual, suma_otros, 'real')

        # 3. Total Entradas
        total_entradas = valores[ID_SALDO_INICIAL]['real'] + valores[ID_TOTAL_RECUPERACION]['real'] + suma_otros
        actualizar_valor_bd(cursor, ID_TOTAL_ENTRADA_EFECTIVO, fecha_actual, total_entradas, 'real')

        # 4. Salidas
        suma_prov = sum(valores[uid]['real'] for uid in IDS_SALIDA_PROVEEDORES)
        actualizar_valor_bd(cursor, ID_TOTAL_SALIDA_PROVEEDORES, fecha_actual, suma_prov, 'real')

        suma_gastos = sum(valores[uid]['real'] for uid in IDS_GASTOS)
        actualizar_valor_bd(cursor, ID_TOTAL_GASTOS, fecha_actual, suma_gastos, 'real')

        suma_creditos = sum(valores[uid]['real'] for uid in IDS_PAGO_CREDITOS)
        actualizar_valor_bd(cursor, ID_TOTAL_PAGO_CREDITOS, fecha_actual, suma_creditos, 'real')

        # 5. Total Salidas Global
        total_salidas = suma_prov + suma_gastos + suma_creditos
        actualizar_valor_bd(cursor, ID_TOTAL_SALIDAS_EFECTIVO, fecha_actual, total_salidas, 'real')

        # 6. Saldo Final
        saldo_final = total_entradas - total_salidas
        actualizar_valor_bd(cursor, ID_TOTAL_DISPONIBLE, fecha_actual, saldo_final, 'real')

        print(f"✅ Cálculos terminados para {mes}/{anio}. Saldo Final: {saldo_final}")

    except Exception as e:
        print(f"❌ Error calculando fórmulas: {e}")

def actualizar_valor_bd(cursor, id_concepto, fecha, monto, tipo='real'):
    columna = 'monto_real' if tipo == 'real' else 'monto_proyectado'
    
    check_sql = "SELECT id_valor FROM flujo_valores WHERE id_concepto = %s AND fecha_reporte = %s"
    cursor.execute(check_sql, (id_concepto, fecha))
    registro = cursor.fetchone()
    
    if registro:
        # Manejo robusto de la respuesta del cursor
        if isinstance(registro, dict): id_valor = registro['id_valor']
        elif isinstance(registro, tuple): id_valor = registro[0]
        else: id_valor = list(registro)[0] # Fallback raro

        sql_up = f"UPDATE flujo_valores SET {columna} = %s WHERE id_valor = %s"
        cursor.execute(sql_up, (monto, id_valor))
    else:
        if tipo == 'real':
            sql_in = "INSERT INTO flujo_valores (id_concepto, fecha_reporte, monto_real, monto_proyectado) VALUES (%s, %s, %s, 0)"
        else:
            sql_in = "INSERT INTO flujo_valores (id_concepto, fecha_reporte, monto_real, monto_proyectado) VALUES (%s, %s, 0, %s)"
        
        cursor.execute(sql_in, (id_concepto, fecha, monto))