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
from fix_totales_2026 import recalcular_formulas_flujo

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
        
        # 2. Obtener nombre para auditoría
        cursor.execute("SELECT nombre_concepto FROM cat_conceptos_unificados WHERE id_concepto = %s", (id_concepto,))
        res_nombre = cursor.fetchone()
        nombre_concepto = res_nombre[0] if res_nombre else f"Concepto {id_concepto}"
        registrar_auditoria(cursor, 'EDICION_CELDA', 'flujo_valores_unificados', id_concepto, f"Editó {nombre_concepto} a ${monto}")

        # 3. CORRECCIÓN: Automatización del recálculo propagado
        f_obj = datetime.strptime(fecha, "%Y-%m-%d")
        # Recalcula desde el mes editado hasta diciembre para propagar saldos iniciales
        for m in range(f_obj.month, 13):
            recalcular_formulas_flujo(conexion, f_obj.year, m)

        conexion.commit()
        return jsonify({"mensaje": "Valor actualizado y saldos propagados correctamente"}), 200

    except Exception as e:
        if conexion: conexion.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if conexion: conexion.close()

# ==============================================================================
# 5. SINCRONIZACIÓN CON ODOO (CORREGIDO: CONVERSIÓN A ENTEROS)
# ==============================================================================
@dashboard_flujo_bp.route('/sincronizar-odoo', methods=['POST'])
def sincronizar_odoo():
    data = request.get_json()
    try:
        anio = int(data.get('anio'))
        mes = int(data.get('mes'))
    except:
        return jsonify({"mensaje": "Año o mes inválidos"}), 400

    fecha_inicio = f"{anio}-{mes:02d}-01"
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    fecha_fin = f"{anio}-{mes:02d}-{ultimo_dia}"
    
    conexion = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        
        # 1. Traer conceptos con mapeo Odoo
        cursor.execute("SELECT id_concepto, categoria, codigo_cuenta_odoo FROM cat_conceptos_unificados WHERE codigo_cuenta_odoo > ''")
        conceptos = cursor.fetchall()
        
        cursor_up = conexion.cursor()
        for c in conceptos:
            # Determinamos si es ingreso por categoría
            es_ingreso = not any(x in c['categoria'].lower() for x in ['egreso', 'gasto', 'costo', 'pasivo'])
            saldo = obtener_saldo_cuenta_odoo(c['codigo_cuenta_odoo'], fecha_inicio, fecha_fin, es_ingreso=es_ingreso)
            
            # Actualizamos sin borrar (Update if exists, else Insert)
            actualizar_valor_bd(cursor_up, c['id_concepto'], fecha_inicio, saldo, 'real')

        # 2. AUTOMATIZACIÓN: Propagar recálculo al resto del año tras el Sync
        for m in range(mes, 13):
            recalcular_formulas_flujo(conexion, anio, m)

        conexion.commit()
        return jsonify({"mensaje": "Sincronización y recálculo anual finalizado"}), 200
    except Exception as e:
        if conexion: conexion.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if conexion: conexion.close()

# ==============================================================================
# LÓGICA DE CÁLCULO DE FÓRMULAS (EN TABLAS UNIFICADAS)
# ==============================================================================
def recalcular_formulas_flujo(conexion, anio, mes):
    cursor = conexion.cursor(dictionary=True)
    fecha_actual = f"{anio}-{mes:02d}-01"
    
    # Cálculos de fecha anterior para arrastre de saldo
    if mes == 1: mes_ant, anio_ant = 12, anio - 1
    else: mes_ant, anio_ant = mes - 1, anio
    fecha_anterior = f"{anio_ant}-{mes_ant:02d}-01"

    try:
        # Definición de IDs Maestro
        ID_SALDO_INICIAL, ID_SALDO_FINAL = 1, 99
        ID_VENTAS, ID_RECUPERACION, ID_TOTAL_ENTRADAS = 2, 3, 8
        IDS_OTROS = [4, 5, 6, 7]
        IDS_PROVEEDORES = [20, 21, 22, 23, 24, 25]
        IDS_OPERATIVOS = [40, 41, 42, 43]
        ID_TOTAL_GASTOS_OPER = 49 # Subtotal solicitado
        ID_TOTAL_SALIDAS = 90

        # A. Obtener saldo final del mes anterior (Arrastre)
        cursor.execute("SELECT monto_real FROM flujo_valores_unificados WHERE id_concepto = %s AND fecha_reporte = %s", (ID_SALDO_FINAL, fecha_anterior))
        res_prev = cursor.fetchone()
        saldo_arrastre = float(res_prev['monto_real']) if res_prev else 0.0

        # Actualizar Saldo Inicial del mes actual
        actualizar_valor_bd(cursor, ID_SALDO_INICIAL, fecha_actual, saldo_arrastre, 'real')
        actualizar_valor_bd(cursor, ID_SALDO_INICIAL, fecha_actual, saldo_arrastre, 'proyectado')

        # B. Cargar valores del mes para cálculos
        cursor.execute("SELECT id_concepto, monto_real, monto_proyectado FROM flujo_valores_unificados WHERE fecha_reporte = %s", (fecha_actual,))
        valores = defaultdict(lambda: {'real': 0.0, 'proy': 0.0})
        for r in cursor.fetchall():
            valores[r['id_concepto']]['real'] = float(r['monto_real'] or 0)
            valores[r['id_concepto']]['proy'] = float(r['monto_proyectado'] or 0)

        for tipo in ['real', 'proy']:
            # C. Cálculo Entradas
            v_ventas = valores[ID_VENTAS][tipo]
            actualizar_valor_bd(cursor, ID_RECUPERACION, fecha_actual, v_ventas, tipo)
            
            s_otros = sum(valores[uid][tipo] for uid in IDS_OTROS)
            t_entradas = round(saldo_arrastre + v_ventas + s_otros, 2)
            actualizar_valor_bd(cursor, ID_TOTAL_ENTRADAS, fecha_actual, t_entradas, tipo)

            # D. Cálculo Salidas con Subtotal 49
            s_prov = sum(valores[uid][tipo] for uid in IDS_PROVEEDORES)
            s_oper = round(sum(valores[uid][tipo] for uid in IDS_OPERATIVOS), 2)
            
            # Guardamos Subtotal de Gastos (ID 49)
            actualizar_valor_bd(cursor, ID_TOTAL_GASTOS_OPER, fecha_actual, s_oper, tipo)
            
            t_salidas = round(s_prov + s_oper + sum(valores[uid][tipo] for uid in [50, 51, 52, 60]), 2)
            actualizar_valor_bd(cursor, ID_TOTAL_SALIDAS, fecha_actual, t_salidas, tipo)

            # E. Saldo Final (ID 99)
            disp = round(t_entradas - t_salidas, 2)
            actualizar_valor_bd(cursor, ID_SALDO_FINAL, fecha_actual, disp, tipo)

    except Exception as e:
        print(f"Error en fórmulas {mes}/{anio}: {e}")

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