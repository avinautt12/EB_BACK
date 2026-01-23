from flask import Blueprint, jsonify, request
from db_conexion import obtener_conexion
from decimal import Decimal
from datetime import date, datetime
from collections import defaultdict
# Importamos la función de auditoría que creamos antes
from utils.jwt_utils import registrar_auditoria, verificar_token
import calendar


try:
    from utils.odoo_utils import obtener_saldo_cuenta_odoo
except ImportError:
    # Por si acaso lo tienes en la raíz
    from utils.odoo_utils import obtener_saldo_cuenta_odoo

# Definimos UN SOLO Blueprint para todo el módulo de flujo
dashboard_flujo_bp = Blueprint('dashboard_flujo_bp', __name__, url_prefix='/flujo')

# ==============================================================================
# 1. LECTURA: TABLERO MENSUAL (Proyectado vs Real de un mes)
# ==============================================================================
@dashboard_flujo_bp.route('/tablero-mensual', methods=['GET'])
def obtener_tablero_mensual():
    """
    Obtiene el comparativo (Proyectado vs Real) para un mes específico.
    Parámetro esperado: ?fecha=2025-12-01
    """
    conexion = None
    try:
        fecha_reporte = request.args.get('fecha', '2025-03-01') 
        
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
# 2. LECTURA: PROYECCIÓN ANUAL (Matriz completa)
# ==============================================================================
@dashboard_flujo_bp.route('/proyeccion-anual', methods=['GET'])
def obtener_proyeccion_anual():
    conexion = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)

        # 1. Obtener Columnas
        cursor.execute("SELECT DISTINCT fecha_reporte FROM flujo_valores ORDER BY fecha_reporte ASC")
        fechas_db = cursor.fetchall()
        columnas_fechas = [f['fecha_reporte'].isoformat() for f in fechas_db]

        # 2. Obtener Datos
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

        # 3. Procesamiento
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

        # 4. Convertir a lista ordenada
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
# 3. ESCRITURA: CREAR CONCEPTO (CON AUDITORÍA)
# ==============================================================================
@dashboard_flujo_bp.route('/conceptos', methods=['POST'])
def crear_concepto():

    auth_header = request.headers.get('Authorization')
    token = auth_header.split(" ")[1] if auth_header and " " in auth_header else None
    
    if not token or not verificar_token(token):
        return jsonify({'error': 'Tu sesión ha expirado. Recarga la página.'}), 401
    # ---------------------------

    data = request.get_json()
    conexion = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        
        sql = "INSERT INTO cat_conceptos (nombre_concepto, categoria, orden_reporte) VALUES (%s, %s, %s)"
        cursor.execute(sql, (
            data.get('nombre'),
            data.get('categoria'), 
            data.get('orden', 99)
        ))
        
        id_nuevo = cursor.lastrowid
        
        # --- AUDITORÍA ---
        desc = f"Creó el concepto '{data.get('nombre')}' en categoría '{data.get('categoria')}'"
        registrar_auditoria(cursor, 'CREAR_CONCEPTO', 'cat_conceptos', id_nuevo, desc)
        
        conexion.commit()
        return jsonify({"mensaje": "Concepto creado correctamente"}), 201

    except Exception as e:
        if conexion: conexion.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if conexion: conexion.close()

# ==============================================================================
# 4. ESCRITURA: GUARDAR VALOR (CON AUDITORÍA)
# ==============================================================================
@dashboard_flujo_bp.route('/guardar-valor', methods=['POST'])
def guardar_valor():

    auth_header = request.headers.get('Authorization')
    token = auth_header.split(" ")[1] if auth_header and " " in auth_header else None
    
    if not token or not verificar_token(token):
        return jsonify({'error': 'Tu sesión ha expirado. Recarga la página.'}), 401
    # ---------------------------

    data = request.get_json()
    conexion = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        id_concepto = data['id_concepto']
        fecha = data['fecha']
        monto = data['monto']
        tipo = data.get('tipo', 'real') 

        check_sql = "SELECT id_valor FROM flujo_valores WHERE id_concepto = %s AND fecha_reporte = %s"
        cursor.execute(check_sql, (id_concepto, fecha))
        resultado = cursor.fetchone()

        if resultado:
            # UPDATE
            id_valor = resultado[0] 
            columna = "monto_real" if tipo == 'real' else "monto_proyectado"
            
            update_sql = f"UPDATE flujo_valores SET {columna} = %s WHERE id_valor = %s"
            cursor.execute(update_sql, (monto, id_valor))
            
            # --- AUDITORÍA ---
            desc = f"Actualizó {columna} a ${monto} para la fecha {fecha}"
            registrar_auditoria(cursor, 'EDICION_CELDA', 'flujo_valores', id_valor, desc)

        else:
            # INSERT
            if tipo == 'real':
                insert_sql = "INSERT INTO flujo_valores (id_concepto, fecha_reporte, monto_real, monto_proyectado) VALUES (%s, %s, %s, 0)"
            else:
                insert_sql = "INSERT INTO flujo_valores (id_concepto, fecha_reporte, monto_real, monto_proyectado) VALUES (%s, %s, 0, %s)"
            
            cursor.execute(insert_sql, (id_concepto, fecha, monto))
            id_nuevo = cursor.lastrowid
            
            # --- AUDITORÍA ---
            desc = f"Creó registro inicial {tipo} con ${monto} para la fecha {fecha}"
            registrar_auditoria(cursor, 'NUEVO_VALOR', 'flujo_valores', id_nuevo, desc)

        conexion.commit()
        return jsonify({"mensaje": "Valor actualizado correctamente"}), 200

    except Exception as e:
        if conexion: conexion.rollback()
        print(f"Error guardar valor: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conexion: conexion.close()

@dashboard_flujo_bp.route('/auditoria', methods=['GET'])
def obtener_historial_auditoria():
    conexion = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        
        # Traemos los últimos 500 movimientos, del más reciente al más antiguo
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
        
        # Convertimos fechas a string ISO para que Angular las entienda
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
# 5. SINCRONIZACIÓN CON ODOO (EL NUEVO ENDPOINT QUE FALTA)
# ==============================================================================
@dashboard_flujo_bp.route('/sincronizar-odoo', methods=['POST'])
def sincronizar_odoo():

    auth_header = request.headers.get('Authorization')
    token = auth_header.split(" ")[1] if auth_header and " " in auth_header else None
    
    if not token or not verificar_token(token):
        return jsonify({'error': 'Tu sesión ha expirado. Recarga la página.'}), 401
    # ---------------------------

    print("🔵 INICIANDO SINCRONIZACIÓN CON ODOO...")
    data = request.get_json()
    anio = data.get('anio')
    mes = data.get('mes')
    
    if not anio or not mes:
        return jsonify({"mensaje": "Faltan datos de año o mes"}), 400

    # Calculamos fechas (Primer y último día del mes)
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    fecha_inicio = f"{anio}-{mes:02d}-01"
    fecha_fin = f"{anio}-{mes:02d}-{ultimo_dia}"
    
    print(f"📅 Fecha: {fecha_inicio} al {fecha_fin}")
    
    conexion = None
    actualizados = 0
    errores = 0
    
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        
        # 1. Traer conceptos que tengan codigo_cuenta_odoo configurado
        cursor.execute("SELECT id_concepto, nombre_concepto, codigo_cuenta_odoo FROM cat_conceptos WHERE codigo_cuenta_odoo IS NOT NULL AND codigo_cuenta_odoo != ''")
        conceptos_mapeados = cursor.fetchall()
        
        print(f"🔎 Conceptos mapeados encontrados: {len(conceptos_mapeados)}")

        cursor_update = conexion.cursor()
        
        for c in conceptos_mapeados:
            codigo = c['codigo_cuenta_odoo']
            print(f"   -> Consultando '{c['nombre_concepto']}' (Cuenta {codigo})...")
            
            # 2. Llamada a tu script de Odoo (odoo_utils.py)
            saldo_real = obtener_saldo_cuenta_odoo(codigo, fecha_inicio, fecha_fin)
            print(f"      💰 Saldo recibido de Odoo: ${saldo_real:,.2f}")
            
            # 3. Guardar en BD (Upsert: Actualizar si existe, Insertar si no)
            try:
                # Verificar si ya existe el registro para ese concepto y fecha
                check_sql = "SELECT id_valor FROM flujo_valores WHERE id_concepto = %s AND fecha_reporte = %s"
                cursor_update.execute(check_sql, (c['id_concepto'], fecha_inicio))
                resultado = cursor_update.fetchone()

                if resultado:
                    # UPDATE
                    sql_up = "UPDATE flujo_valores SET monto_real = %s WHERE id_valor = %s"
                    cursor_update.execute(sql_up, (saldo_real, resultado[0]))
                else:
                    # INSERT
                    sql_in = "INSERT INTO flujo_valores (id_concepto, fecha_reporte, monto_real, monto_proyectado) VALUES (%s, %s, %s, 0)"
                    cursor_update.execute(sql_in, (c['id_concepto'], fecha_inicio, saldo_real))
                
                actualizados += 1
            except Exception as e_sql:
                print(f"      ❌ Error SQL al guardar: {e_sql}")
                errores += 1

        # Registrar Auditoría Global del proceso
        if actualizados > 0:
            desc = f"Sync Odoo {fecha_inicio}: {actualizados} conceptos actualizados."
            # Usamos un ID 0 o NULL para indicar que fue el sistema
            registrar_auditoria(cursor_update, 'SYNC_ODOO', 'flujo_valores', 0, desc)

        conexion.commit()
        mensaje = f"Sincronización finalizada. {actualizados} actualizados."
        return jsonify({"mensaje": mensaje}), 200

    except Exception as e:
        if conexion: conexion.rollback()
        print(f"❌ Error CRÍTICO en sync: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conexion: conexion.close()