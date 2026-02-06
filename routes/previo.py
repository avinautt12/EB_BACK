from flask import Blueprint, jsonify, request
from models.monitor_odoo_model import obtener_todos_los_registros
from db_conexion import obtener_conexion
from decimal import Decimal

previo_bp = Blueprint('previo', __name__, url_prefix='')

@previo_bp.route('/actualizar_previo', methods=['POST'])
def actualizar_previo():
    conexion = None
    cursor = None
    
    try:
        if not request.is_json:
            return jsonify({'error': 'Se esperaba un JSON'}), 400
        
        data = request.get_json()
        registros = data.get('datos') if isinstance(data, dict) else data
        
        if not isinstance(registros, list) or len(registros) == 0:
            return jsonify({'error': 'No hay registros para actualizar'}), 400
        
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        
        # 1. Limpiar tabla actual
        cursor.execute("TRUNCATE TABLE previo")
        
        registros_insertados = 0
        
        for i, registro in enumerate(registros):
            try:
                if 'clave' not in registro or 'nombre_cliente' not in registro:
                    continue
                
                # --- AQUÍ VA LA LÓGICA DE RECALCULO ---
                # Extraemos los valores necesarios para el cálculo
                meta_inicial = float(registro.get('compra_minima_inicial', 0))
                meta_anual = float(registro.get('compra_minima_anual', 0))
                avance_real = float(registro.get('acumulado_anticipado', 0)) # El valor de $7.3M

                # Calculamos los porcentajes reales
                porcentaje_global_calc = 0
                if meta_inicial > 0:
                    porcentaje_global_calc = int(round((avance_real / meta_inicial) * 100))

                porcentaje_anual_calc = 0
                if meta_anual > 0:
                    porcentaje_anual_calc = int(round((avance_real / meta_anual) * 100))
                # ---------------------------------------

                def get_porcentaje(key, fallback_val=0):
                    value = registro.get(key, 0)
                    if isinstance(value, (float, Decimal)):
                        return int(round(value))
                    return int(value or fallback_val)
                
                cursor.execute("""
                    INSERT INTO previo (
                        clave, evac, nombre_cliente, acumulado_anticipado, nivel,
                        compra_minima_anual, porcentaje_anual,
                        compra_minima_inicial, avance_global, porcentaje_global,
                        compromiso_scott, avance_global_scott, porcentaje_scott,
                        compromiso_jul_ago, avance_jul_ago, porcentaje_jul_ago,
                        compromiso_sep_oct, avance_sep_oct, porcentaje_sep_oct,
                        compromiso_nov_dic, avance_nov_dic, porcentaje_nov_dic,
                        compromiso_ene_feb, avance_ene_feb, porcentaje_ene_feb,
                        compromiso_mar_abr, avance_mar_abr, porcentaje_mar_abr,
                        compromiso_may_jun, avance_may_jun, porcentaje_may_jun,
                        compromiso_apparel_syncros_vittoria, avance_global_apparel_syncros_vittoria,
                        porcentaje_apparel_syncros_vittoria, 
                        compromiso_jul_ago_app, avance_jul_ago_app, porcentaje_jul_ago_app,
                        compromiso_sep_oct_app, avance_sep_oct_app, porcentaje_sep_oct_app,
                        compromiso_nov_dic_app, avance_nov_dic_app, porcentaje_nov_dic_app,
                        compromiso_ene_feb_app, avance_ene_feb_app, porcentaje_ene_feb_app,
                        compromiso_mar_abr_app, avance_mar_abr_app, porcentaje_mar_abr_app,
                        compromiso_may_jun_app, avance_may_jun_app, porcentaje_may_jun_app,
                        es_integral, grupo_integral
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                        %s, %s
                    )
                """, (
                    registro.get('clave'),
                    registro.get('evac'),
                    registro.get('nombre_cliente'),
                    avance_real,
                    registro.get('nivel'),
                    meta_anual,
                    porcentaje_anual_calc, # USAMOS EL CALCULADO
                    meta_inicial,
                    registro.get('avance_global', 0),
                    porcentaje_global_calc, # USAMOS EL CALCULADO
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
                    registro.get('compromiso_ene_feb', 0),
                    registro.get('avance_ene_feb', 0),
                    get_porcentaje('porcentaje_ene_feb'),
                    registro.get('compromiso_mar_abr', 0),
                    registro.get('avance_mar_abr', 0),
                    get_porcentaje('porcentaje_mar_abr'),
                    registro.get('compromiso_may_jun', 0),
                    registro.get('avance_may_jun', 0),
                    get_porcentaje('porcentaje_may_jun'),
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
                    registro.get('compromiso_ene_feb_app', 0),
                    registro.get('avance_ene_feb_app', 0),
                    get_porcentaje('porcentaje_ene_feb_app'),
                    registro.get('compromiso_mar_abr_app', 0),
                    registro.get('avance_mar_abr_app', 0),
                    get_porcentaje('porcentaje_mar_abr_app'),
                    registro.get('compromiso_may_jun_app', 0),
                    registro.get('avance_may_jun_app', 0),
                    get_porcentaje('porcentaje_may_jun_app'),
                    int(bool(registro.get('es_integral', False))),
                    registro.get('grupo_integral')
                ))
                registros_insertados += 1
                
            except Exception as e:
                print(f"Error en registro {i}: {e}")
                continue
        
        conexion.commit()
        return jsonify({'mensaje': f'Actualizados {registros_insertados} registros'}), 200
        
    except Exception as e:
        if conexion: conexion.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conexion: conexion.close()

@previo_bp.route('/obtener_previo', methods=['GET'])
def obtener_previo():
    conexion = None
    cursor = None
    
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        
        # Se agregaron los nuevos campos al SELECT
        cursor.execute("""
            SELECT id, clave, evac, nombre_cliente, acumulado_anticipado, nivel, nivel_cierre_compra_inicial,
                   compra_minima_anual, porcentaje_anual, compra_minima_inicial, avance_global, porcentaje_global,
                   compromiso_scott, avance_global_scott, porcentaje_scott, 
                   compromiso_jul_ago, avance_jul_ago, porcentaje_jul_ago, 
                   compromiso_sep_oct, avance_sep_oct, porcentaje_sep_oct, 
                   compromiso_nov_dic, avance_nov_dic, porcentaje_nov_dic,
                   compromiso_ene_feb, avance_ene_feb, porcentaje_ene_feb,
                   compromiso_mar_abr, avance_mar_abr, porcentaje_mar_abr,
                   compromiso_may_jun, avance_may_jun, porcentaje_may_jun,
                   compromiso_apparel_syncros_vittoria,
                   avance_global_apparel_syncros_vittoria, porcentaje_apparel_syncros_vittoria,
                   compromiso_jul_ago_app, avance_jul_ago_app, porcentaje_jul_ago_app,
                   compromiso_sep_oct_app, avance_sep_oct_app, porcentaje_sep_oct_app,
                   compromiso_nov_dic_app, avance_nov_dic_app, porcentaje_nov_dic_app,
                   compromiso_ene_feb_app, avance_ene_feb_app, porcentaje_ene_feb_app,
                   compromiso_mar_abr_app, avance_mar_abr_app, porcentaje_mar_abr_app,
                   compromiso_may_jun_app, avance_may_jun_app, porcentaje_may_jun_app,
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
        
        # Se agregaron los nuevos campos al SELECT
        cursor.execute("""
            SELECT id, clave, evac, nombre_cliente, acumulado_anticipado, nivel, nivel_cierre_compra_inicial,
                   compra_minima_anual, porcentaje_anual, compra_minima_inicial, avance_global, porcentaje_global,
                   compromiso_scott, avance_global_scott, porcentaje_scott, 
                   compromiso_jul_ago, avance_jul_ago, porcentaje_jul_ago, 
                   compromiso_sep_oct, avance_sep_oct, porcentaje_sep_oct, 
                   compromiso_nov_dic, avance_nov_dic, porcentaje_nov_dic,
                   compromiso_ene_feb, avance_ene_feb, porcentaje_ene_feb,
                   compromiso_mar_abr, avance_mar_abr, porcentaje_mar_abr,
                   compromiso_may_jun, avance_may_jun, porcentaje_may_jun,
                   compromiso_apparel_syncros_vittoria,
                   avance_global_apparel_syncros_vittoria, porcentaje_apparel_syncros_vittoria,
                   compromiso_jul_ago_app, avance_jul_ago_app, porcentaje_jul_ago_app,
                   compromiso_sep_oct_app, avance_sep_oct_app, porcentaje_sep_oct_app,
                   compromiso_nov_dic_app, avance_nov_dic_app, porcentaje_nov_dic_app,
                   compromiso_ene_feb_app, avance_ene_feb_app, porcentaje_ene_feb_app,
                   compromiso_mar_abr_app, avance_mar_abr_app, porcentaje_mar_abr_app,
                   compromiso_may_jun_app, avance_may_jun_app, porcentaje_may_jun_app,
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