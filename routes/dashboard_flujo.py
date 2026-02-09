from flask import Blueprint, jsonify, request
from db_conexion import obtener_conexion
from decimal import Decimal
from datetime import date, datetime
from collections import defaultdict
import calendar
import pandas as pd
from io import BytesIO
from flask import send_file
from openpyxl.utils import get_column_letter

# Importamos utilidades
from utils.jwt_utils import registrar_auditoria, verificar_token

try:
    from utils.odoo_utils import obtener_saldo_cuenta_odoo
except ImportError:
    from utils.odoo_utils import obtener_saldo_cuenta_odoo

dashboard_flujo_bp = Blueprint('dashboard_flujo_bp', __name__, url_prefix='/flujo')

# ==============================================================================
# 1. LECTURA: TABLERO MENSUAL (USANDO TABLAS UNIFICADAS)
# ==============================================================================
@dashboard_flujo_bp.route('/tablero-mensual', methods=['GET'])
def obtener_tablero_mensual():
    conexion = None
    try:
        fecha_reporte = request.args.get('fecha', '2026-01-01') 
        
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        
        # CAMBIO: Usamos cat_conceptos_unificados y flujo_valores_unificados
        sql = """
            SELECT 
                c.id_concepto,
                c.nombre_concepto,
                c.categoria,
                c.orden_reporte,
                COALESCE(v.monto_proyectado, 0) as proyectado,
                COALESCE(v.monto_real, 0) as real_val
            FROM cat_conceptos_unificados c
            LEFT JOIN flujo_valores_unificados v 
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
                # Alerta visual simple: Negativo en Ingresos es malo
                "alerta": "negativa" if diferencia < 0 and 'Ingresos' in row['categoria'] else "normal"
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
# 2. LECTURA: PROYECCIÓN ANUAL (USANDO TABLAS UNIFICADAS)
# ==============================================================================
@dashboard_flujo_bp.route('/proyeccion-anual', methods=['GET'])
def obtener_proyeccion_anual():
    conexion = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)

        # CAMBIO: Tabla unificada
        cursor.execute("SELECT DISTINCT fecha_reporte FROM flujo_valores_unificados ORDER BY fecha_reporte ASC")
        fechas_db = cursor.fetchall()
        columnas_fechas = [f['fecha_reporte'].isoformat() for f in fechas_db]

        # CAMBIO: Tablas unificadas
        sql = """
            SELECT 
                c.id_concepto, 
                c.nombre_concepto, 
                c.categoria,
                c.orden_reporte,
                v.fecha_reporte,
                v.monto_proyectado,
                v.monto_real
            FROM cat_conceptos_unificados c
            LEFT JOIN flujo_valores_unificados v ON c.id_concepto = v.id_concepto
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
# 3. ESCRITURA: GUARDAR VALOR (EN TABLAS UNIFICADAS)
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

        # 1. Guardar el valor en la tabla UNIFICADA
        actualizar_valor_bd(cursor, id_concepto, fecha, monto, tipo)
        
        # 2. Auditoría (busca nombre en la tabla UNIFICADA)
        cursor.execute("SELECT nombre_concepto FROM cat_conceptos_unificados WHERE id_concepto = %s", (id_concepto,))
        res_nombre = cursor.fetchone()
        
        nombre_concepto = res_nombre[0] if res_nombre else f"Concepto {id_concepto}"

        desc = f"Editó {nombre_concepto} ({tipo}) a ${monto}"
        registrar_auditoria(cursor, 'EDICION_CELDA', 'flujo_valores_unificados', id_concepto, desc)

        # 3. Recalcular Fórmulas UNIFICADAS
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
# 5. SINCRONIZACIÓN CON ODOO (CORREGIDO: CONVERSIÓN A ENTEROS)
# ==============================================================================
@dashboard_flujo_bp.route('/sincronizar-odoo', methods=['POST'])
def sincronizar_odoo():
    auth_header = request.headers.get('Authorization')
    token = auth_header.split(" ")[1] if auth_header and " " in auth_header else None
    
    if not token or not verificar_token(token):
        return jsonify({'error': 'Tu sesión ha expirado.'}), 401

    print("🔵 INICIANDO SINCRONIZACIÓN CON ODOO (MODO UNIFICADO)...")
    data = request.get_json()
    
    # --- CORRECCIÓN AQUÍ: Convertimos a int() para evitar el error ---
    try:
        anio = int(data.get('anio'))
        mes = int(data.get('mes'))
    except (ValueError, TypeError):
        return jsonify({"mensaje": "El año y el mes deben ser números válidos"}), 400
    
    if not anio or not mes:
        return jsonify({"mensaje": "Faltan datos de año o mes"}), 400

    # Ahora sí funcionará porque son enteros
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    
    fecha_inicio = f"{anio}-{mes:02d}-01"
    fecha_fin = f"{anio}-{mes:02d}-{ultimo_dia}"
    
    conexion = None
    actualizados = 0
    errores = 0
    
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        
        # 1. Traer conceptos configurados DESDE LA TABLA UNIFICADA
        cursor.execute("""
            SELECT id_concepto, nombre_concepto, categoria, codigo_cuenta_odoo 
            FROM cat_conceptos_unificados
            WHERE codigo_cuenta_odoo IS NOT NULL AND codigo_cuenta_odoo != ''
        """)
        conceptos_mapeados = cursor.fetchall()
        
        cursor_update = conexion.cursor()
        
        for c in conceptos_mapeados:
            codigo = c['codigo_cuenta_odoo']
            cat_lower = c['categoria'].lower() if c['categoria'] else ''
            
            es_ingreso = True
            if any(x in cat_lower for x in ['egreso', 'gasto', 'costo', 'pasivo', 'proveedor']):
                es_ingreso = False
            
            print(f"   -> Sincronizando '{c['nombre_concepto']}'...")
            
            saldo_real = obtener_saldo_cuenta_odoo(codigo, fecha_inicio, fecha_fin, es_ingreso=es_ingreso)
            
            try:
                # Guardar en flujo_valores_unificados
                actualizar_valor_bd(cursor_update, c['id_concepto'], fecha_inicio, saldo_real, 'real')
                actualizados += 1
            except Exception as e_sql:
                print(f"❌ Error SQL ID {c['id_concepto']}: {e_sql}")
                errores += 1

        if actualizados > 0:
            desc = f"Sync Odoo {fecha_inicio}: {actualizados} actualizados."
            registrar_auditoria(cursor_update, 'SYNC_ODOO', 'flujo_valores_unificados', 0, desc)

        # 2. Recalcular Fórmulas
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
# LÓGICA DE CÁLCULO DE FÓRMULAS (EN TABLAS UNIFICADAS)
# ==============================================================================
def recalcular_formulas_flujo(conexion, anio, mes):
    """
    Realiza las sumas y restas automáticas en las TABLAS UNIFICADAS.
    Estructura de IDs (1-99)
    """
    print(f"🧮 Recalculando fórmulas UNIFICADAS para {mes}/{anio}...")
    cursor = conexion.cursor(dictionary=True)
    
    fecha_actual = f"{anio}-{mes:02d}-01"
    
    if mes == 1:
        mes_anterior, anio_anterior = 12, anio - 1
    else:
        mes_anterior, anio_anterior = mes - 1, anio
        
    fecha_anterior = f"{anio_anterior}-{mes_anterior:02d}-01"

    try:
        # --- DEFINICIÓN DE IDs (Tabla Unificada) ---
        ID_SALDO_INICIAL = 1
        ID_SALDO_FINAL = 99

        ID_VENTAS = 2
        ID_TOTAL_RECUPERACION = 3
        IDS_OTROS_INGRESOS = [4, 5, 6, 7] 
        ID_TOTAL_ENTRADAS = 8

        IDS_PROVEEDORES = [20, 21, 22, 23, 24, 25]
        IDS_OPERATIVOS = [40, 41, 42, 43]
        IDS_FINANCIEROS = [50, 51, 52]
        IDS_MOVIMIENTOS = [60]
        ID_TOTAL_SALIDAS = 90

        # ------------------------------------------------------------------

        # 1. TRAER VALORES ACTUALES (De la tabla unificada)
        sql_fetch = "SELECT id_concepto, monto_real, monto_proyectado FROM flujo_valores_unificados WHERE fecha_reporte = %s"
        cursor.execute(sql_fetch, (fecha_actual,))
        rows = cursor.fetchall()
        
        valores = defaultdict(lambda: {'real': 0.0, 'proy': 0.0})
        for r in rows:
            valores[r['id_concepto']]['real'] = float(r['monto_real'] or 0)
            valores[r['id_concepto']]['proy'] = float(r['monto_proyectado'] or 0)

        # A. ARRASTRE DE SALDOS (Desde tabla unificada)
        sql_ant = "SELECT monto_real FROM flujo_valores_unificados WHERE id_concepto = %s AND fecha_reporte = %s"
        cursor.execute(sql_ant, (ID_SALDO_FINAL, fecha_anterior))
        res_prev = cursor.fetchone()
        
        saldo_anterior = float(res_prev['monto_real']) if res_prev else 0.0
        
        if not (anio == 2026 and mes == 1):
            actualizar_valor_bd(cursor, ID_SALDO_INICIAL, fecha_actual, saldo_anterior, 'real')
            actualizar_valor_bd(cursor, ID_SALDO_INICIAL, fecha_actual, saldo_anterior, 'proyectado')
            valores[ID_SALDO_INICIAL]['real'] = saldo_anterior
            valores[ID_SALDO_INICIAL]['proy'] = saldo_anterior

        # B. CÁLCULO DE ENTRADAS
        for tipo in ['real', 'proy']:
            v_ventas = valores[ID_VENTAS][tipo]
            actualizar_valor_bd(cursor, ID_TOTAL_RECUPERACION, fecha_actual, v_ventas, tipo)
            valores[ID_TOTAL_RECUPERACION][tipo] = v_ventas

            s_otros = sum(valores[uid][tipo] for uid in IDS_OTROS_INGRESOS)
            
            t_entradas = valores[ID_SALDO_INICIAL][tipo] + v_ventas + s_otros
            actualizar_valor_bd(cursor, ID_TOTAL_ENTRADAS, fecha_actual, t_entradas, tipo)
            valores[ID_TOTAL_ENTRADAS][tipo] = t_entradas

        # C. CÁLCULO DE SALIDAS
        for tipo in ['real', 'proy']:
            s_proveedores = sum(valores[uid][tipo] for uid in IDS_PROVEEDORES)
            s_operativos = sum(valores[uid][tipo] for uid in IDS_OPERATIVOS)
            s_financieros = sum(valores[uid][tipo] for uid in IDS_FINANCIEROS)
            s_movimientos = sum(valores[uid][tipo] for uid in IDS_MOVIMIENTOS)

            t_salidas = s_proveedores + s_operativos + s_financieros + s_movimientos
            actualizar_valor_bd(cursor, ID_TOTAL_SALIDAS, fecha_actual, t_salidas, tipo)
            valores[ID_TOTAL_SALIDAS][tipo] = t_salidas

        # D. SALDO FINAL DISPONIBLE
        for tipo in ['real', 'proy']:
            saldo_final = valores[ID_TOTAL_ENTRADAS][tipo] - valores[ID_TOTAL_SALIDAS][tipo]
            actualizar_valor_bd(cursor, ID_SALDO_FINAL, fecha_actual, saldo_final, tipo)
            valores[ID_SALDO_FINAL][tipo] = saldo_final

        print(f"✅ Cálculos UNIFICADOS terminados para {mes}/{anio}.")

    except Exception as e:
        print(f"❌ Error calculando fórmulas: {e}")

# HELPER: Actualizar Valor en BD (UNIFICADA)
def actualizar_valor_bd(cursor, id_concepto, fecha, monto, tipo='real'):
    columna = 'monto_real' if tipo == 'real' else 'monto_proyectado'
    
    # CAMBIO: Apuntamos a la tabla unificada
    check_sql = "SELECT id_valor FROM flujo_valores_unificados WHERE id_concepto = %s AND fecha_reporte = %s"
    cursor.execute(check_sql, (id_concepto, fecha))
    registro = cursor.fetchone()
    
    if registro:
        if isinstance(registro, dict): id_valor = registro['id_valor']
        else: id_valor = registro[0]
        
        sql_up = f"UPDATE flujo_valores_unificados SET {columna} = %s WHERE id_valor = %s"
        cursor.execute(sql_up, (monto, id_valor))
    else:
        if tipo == 'real':
            sql_in = "INSERT INTO flujo_valores_unificados (id_concepto, fecha_reporte, monto_real, monto_proyectado) VALUES (%s, %s, %s, 0)"
        else:
            sql_in = "INSERT INTO flujo_valores_unificados (id_concepto, fecha_reporte, monto_real, monto_proyectado) VALUES (%s, %s, 0, %s)"
        cursor.execute(sql_in, (id_concepto, fecha, monto))

# ==============================================================================
# 6. GENERACIÓN DE REPORTES EN EXCEL (FLUJO UNIFICADO)
# ==============================================================================
@dashboard_flujo_bp.route('/reporte-excel', methods=['GET'])
def exportar_excel():
    conexion = None
    try:
        fecha_inicio = request.args.get('inicio')
        fecha_fin = request.args.get('fin')

        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        
        # SQL MEJORADO: Usamos LEFT JOIN para que salgan todos los conceptos
        # y filtramos la fecha dentro del JOIN para evitar duplicados
        sql = """
            SELECT 
                COALESCE(DATE_FORMAT(v.fecha_reporte, '%Y-%m-%d'), %s) AS Fecha,
                c.categoria AS Categoria,
                c.nombre_concepto AS Concepto,
                CAST(COALESCE(v.monto_proyectado, 0) AS DECIMAL(15,2)) AS Proyectado,
                CAST(COALESCE(v.monto_real, 0) AS DECIMAL(15,2)) AS Monto_Real,
                CAST((COALESCE(v.monto_real, 0) - COALESCE(v.monto_proyectado, 0)) AS DECIMAL(15,2)) AS Diferencia
            FROM cat_conceptos_unificados c
            LEFT JOIN flujo_valores_unificados v 
                ON c.id_concepto = v.id_concepto 
                AND v.fecha_reporte BETWEEN %s AND %s
            ORDER BY v.fecha_reporte DESC, c.orden_reporte ASC
        """
        
        cursor.execute(sql, (fecha_inicio, fecha_inicio, fecha_fin))
        data = cursor.fetchall()
        
        if not data:
            return jsonify({'error': 'No hay datos'}), 404

        df = pd.DataFrame(data)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Flujo de Efectivo')
            worksheet = writer.sheets['Flujo de Efectivo']

            # Formato de Moneda exacto: $#,##0.00
            currency_format = '$#,##0.00'
            
            for row in range(2, len(df) + 2):
                # Aplicamos a Proyectado (D), Real (E) y Diferencia (F)
                for col in ['D', 'E', 'F']:
                    cell = worksheet[f'{col}{row}']
                    cell.number_format = currency_format

            # Ajuste de columnas
            for idx, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.column_dimensions[get_column_letter(idx + 1)].width = max_len

        output.seek(0)
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name=f"Reporte_Flujo_{fecha_inicio}.xlsx")
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conexion: conexion.close()

@dashboard_flujo_bp.route('/verificar-permiso/<int:id_usuario>', methods=['GET'])
def verificar_permiso_joker(id_usuario):
    conexion = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        
        # Consultamos el campo flujo que agregamos a la tabla usuarios
        sql = "SELECT flujo FROM usuarios WHERE id = %s"
        cursor.execute(sql, (id_usuario,))
        usuario = cursor.fetchone()
        
        if not usuario:
            return jsonify({"permiso": 0, "error": "Usuario no encontrado"}), 404
            
        # Retorna 1 si es Joker, 0 si es captura limitada
        return jsonify({"permiso": usuario['flujo']}), 200

    except Exception as e:
        print(f"Error verificando permiso: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conexion: conexion.close()