from flask import Blueprint, jsonify, request
from models.monitor_odoo_model import obtener_todos_los_registros
from db_conexion import obtener_conexion
from decimal import Decimal

previo_bp = Blueprint('previo', __name__, url_prefix='')


@previo_bp.route('/monitor_odoo_calculado', methods=['GET'])
def monitor_calculado():
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        datos = obtener_todos_los_registros(cursor)
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
    except Exception as e:
        print("Error general en monitor_calculado:", str(e))
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

@previo_bp.route('/actualizar_previo', methods=['POST'])
def actualizar_previo():
    conexion = None
    cursor = None
    
    try:
        # Verificar que se recibió data JSON
        if not request.is_json:
            return jsonify({'error': 'Se esperaba un JSON en el cuerpo de la solicitud'}), 400
        
        data = request.get_json()
        
        # El frontend envía { datos: [...] }, así que extraemos el array
        if isinstance(data, dict) and 'datos' in data:
            registros = data['datos']
        elif isinstance(data, list):
            registros = data
        else:
            return jsonify({'error': 'Formato de datos incorrecto. Se esperaba una lista o {datos: [...]}'}), 400
        
        # Validar estructura básica de los datos
        if not isinstance(registros, list):
            return jsonify({'error': 'Los datos deben ser una lista de registros'}), 400
            
        if len(registros) == 0:
            return jsonify({'error': 'No se recibieron registros para actualizar'}), 400
        
        print(f"Recibidos {len(registros)} registros para actualizar")
        
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        
        # 1. Eliminar todos los registros existentes
        cursor.execute("TRUNCATE TABLE previo")
        
        # 2. Insertar los nuevos registros
        registros_insertados = 0
        
        for i, registro in enumerate(registros):
            try:
                # Validar campos obligatorios
                if 'clave' not in registro or 'nombre_cliente' not in registro:
                    print(f"Registro {i} omitido: falta clave o nombre_cliente")
                    continue
                
                # Asegurar que los porcentajes sean enteros
                def get_porcentaje(key):
                    value = registro.get(key, 0)
                    # Si es string con %, eliminar el % y convertir a int
                    if isinstance(value, str) and '%' in value:
                        return int(float(value.replace('%', '').strip()))
                    # Si es float o decimal, redondear y convertir a int
                    if isinstance(value, (float, Decimal)):
                        return int(round(value))
                    return int(value or 0)
                
                cursor.execute("""
                    INSERT INTO previo (
                        clave, evac, nombre_cliente, acumulado_anticipado, nivel,
                        nivel_cierre_compra_inicial, compra_minima_anual, porcentaje_anual,
                        compra_minima_inicial, avance_global, porcentaje_global,
                        compromiso_scott, avance_global_scott, porcentaje_scott,
                        compromiso_jul_ago, avance_jul_ago, porcentaje_jul_ago,
                        compromiso_sep_oct, avance_sep_oct, porcentaje_sep_oct,
                        compromiso_nov_dic, avance_nov_dic, porcentaje_nov_dic,
                        compromiso_apparel_syncros_vittoria, avance_global_apparel_syncros_vittoria,
                        porcentaje_apparel_syncros_vittoria, compromiso_jul_ago_app,
                        avance_jul_ago_app, porcentaje_jul_ago_app, compromiso_sep_oct_app,
                        avance_sep_oct_app, porcentaje_sep_oct_app, compromiso_nov_dic_app,
                        avance_nov_dic_app, porcentaje_nov_dic_app, acumulado_syncros,
                        acumulado_apparel, acumulado_vittoria, acumulado_bold, es_integral,
                        grupo_integral
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    registro.get('clave'),
                    registro.get('evac'),
                    registro.get('nombre_cliente'),
                    registro.get('acumulado_anticipado', 0),
                    registro.get('nivel'),
                    registro.get('nivel_cierre_compra_inicial'),
                    registro.get('compra_minima_anual', 0),
                    get_porcentaje('porcentaje_anual'),
                    registro.get('compra_minima_inicial', 0),
                    registro.get('avance_global', 0),
                    get_porcentaje('porcentaje_global'),
                    registro.get('compromiso_scott', 0),
                    registro.get('avance_global_scott', 0),
                    get_porcentaje('porcentaje_scott'),
                    registro.get('compromiso_jul_ago', 0),
                    registro.get('avance_jul_ago', 0),
                    get_porcentaje('porcentaje_jul_ago'),
                    registro.get('compromiso_sep_oct', 0),
                    registro.get('avance_sep_oct', 0),
                    get_porcentaje('porcentaje_sep_oct'),
                    registro.get('compromiso_nov_dic', 0),
                    registro.get('avance_nov_dic', 0),
                    get_porcentaje('porcentaje_nov_dic'),
                    registro.get('compromiso_apparel_syncros_vittoria', 0),
                    registro.get('avance_global_apparel_syncros_vittoria', 0),
                    get_porcentaje('porcentaje_apparel_syncros_vittoria'),
                    registro.get('compromiso_jul_ago_app', 0),
                    registro.get('avance_jul_ago_app', 0),
                    get_porcentaje('porcentaje_jul_ago_app'),
                    registro.get('compromiso_sep_oct_app', 0),
                    registro.get('avance_sep_oct_app', 0),
                    get_porcentaje('porcentaje_sep_oct_app'),
                    registro.get('compromiso_nov_dic_app', 0),
                    registro.get('avance_nov_dic_app', 0),
                    get_porcentaje('porcentaje_nov_dic_app'),
                    registro.get('acumulado_syncros', 0),
                    registro.get('acumulado_apparel', 0),
                    registro.get('acumulado_vittoria', 0),
                    registro.get('acumulado_bold', 0),
                    int(bool(registro.get('es_integral', False))),
                    registro.get('grupo_integral')
                ))
                
                registros_insertados += 1
                
            except Exception as insert_error:
                print(f"Error insertando registro {i} (clave: {registro.get('clave', 'N/A')}): {insert_error}")
                # Continuamos con el siguiente registro en lugar de fallar completamente
                continue
            finally:
                if cursor:
                    cursor.close()
                if conexion and conexion.is_connected():
                    conexion.close()
        
        conexion.commit()
        return jsonify({
            'mensaje': f'Datos actualizados correctamente. {registros_insertados} de {len(registros)} registros insertados.'
        }), 200
    
    except Exception as e:
        print(f"Error general: {str(e)}")
        if conexion:
            conexion.rollback()
        return jsonify({'error': str(e)}), 500
    
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

@previo_bp.route('/obtener_previo', methods=['GET'])
def obtener_previo():
    conexion = None
    cursor = None
    
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        
        # Seleccionar todos los campos menos los últimos 2
        cursor.execute("""
            SELECT id, clave, evac, nombre_cliente, acumulado_anticipado, nivel, nivel_cierre_compra_inicial,
                   compra_minima_anual, porcentaje_anual, compra_minima_inicial, avance_global, porcentaje_global,
                   compromiso_scott, avance_global_scott, porcentaje_scott, compromiso_jul_ago, avance_jul_ago,
                   porcentaje_jul_ago, compromiso_sep_oct, avance_sep_oct, porcentaje_sep_oct, compromiso_nov_dic,
                   avance_nov_dic, porcentaje_nov_dic, compromiso_apparel_syncros_vittoria,
                   avance_global_apparel_syncros_vittoria, porcentaje_apparel_syncros_vittoria,
                   compromiso_jul_ago_app, avance_jul_ago_app, porcentaje_jul_ago_app,
                   compromiso_sep_oct_app, avance_sep_oct_app, porcentaje_sep_oct_app,
                   compromiso_nov_dic_app, avance_nov_dic_app, porcentaje_nov_dic_app,
                   acumulado_syncros, acumulado_apparel, acumulado_vittoria, acumulado_bold
            FROM previo
        """)
        
        registros = cursor.fetchall()
        return jsonify(registros), 200
        
    except Exception as e:
        print(f"Error obteniendo datos: {str(e)}")
        return jsonify({'error': str(e)}), 500
        
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@previo_bp.route('/obtener_previo_int', methods=['GET'])
def obtener_previo_int():
    conexion = None
    cursor = None
    
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        
        # Seleccionar todos los campos menos los últimos 2, excluyendo Integrales 1, 2 y 3
        cursor.execute("""
            SELECT id, clave, evac, nombre_cliente, acumulado_anticipado, nivel, nivel_cierre_compra_inicial,
                   compra_minima_anual, porcentaje_anual, compra_minima_inicial, avance_global, porcentaje_global,
                   compromiso_scott, avance_global_scott, porcentaje_scott, compromiso_jul_ago, avance_jul_ago,
                   porcentaje_jul_ago, compromiso_sep_oct, avance_sep_oct, porcentaje_sep_oct, compromiso_nov_dic,
                   avance_nov_dic, porcentaje_nov_dic, compromiso_apparel_syncros_vittoria,
                   avance_global_apparel_syncros_vittoria, porcentaje_apparel_syncros_vittoria,
                   compromiso_jul_ago_app, avance_jul_ago_app, porcentaje_jul_ago_app,
                   compromiso_sep_oct_app, avance_sep_oct_app, porcentaje_sep_oct_app,
                   compromiso_nov_dic_app, avance_nov_dic_app, porcentaje_nov_dic_app,
                   acumulado_syncros, acumulado_apparel, acumulado_vittoria, acumulado_bold
            FROM previo
            WHERE clave NOT IN ('Integral 1', 'Integral 2', 'Integral 3')
        """)
        
        registros = cursor.fetchall()
        return jsonify(registros), 200
        
    except Exception as e:
        print(f"Error obteniendo datos (excluyendo integrales): {str(e)}")
        return jsonify({'error': str(e)}), 500
        
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()
