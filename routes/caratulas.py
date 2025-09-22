from flask import Blueprint, jsonify, request, Response
from db_conexion import obtener_conexion
from decimal import Decimal
import json
from weasyprint import HTML
from utils.email_utils import crear_cuerpo_email

caratulas_bp = Blueprint('caratulas', __name__, url_prefix='')

@caratulas_bp.route('/caratula_evac', methods=['GET'])
def buscar_caratula_evac():
    try:
        # Obtener parámetros
        clave = request.args.get('clave')
        nombre_cliente = request.args.get('nombre_cliente')
        
        # Validar que al menos un parámetro esté presente
        if not clave and not nombre_cliente:
            return jsonify({
                'error': 'Se requiere al menos uno de los parámetros: clave o nombre_cliente'
            }), 400

        # Conexión a BD
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)

        # Construir consulta dinámica
        query = """
        SELECT 
            clave,
            evac,
            nombre_cliente,
            nivel,
            compra_minima_anual,
            compromiso_scott,
            avance_global_scott,
            porcentaje_scott,
            compromiso_apparel_syncros_vittoria,
            avance_global_apparel_syncros_vittoria,
            porcentaje_apparel_syncros_vittoria,
            compromiso_jul_ago,
            avance_jul_ago,
            porcentaje_jul_ago,
            compromiso_sep_oct,
            avance_sep_oct,
            porcentaje_sep_oct,
            compromiso_nov_dic,
            avance_nov_dic,
            porcentaje_nov_dic,
            compromiso_jul_ago_app,
            avance_jul_ago_app,
            porcentaje_jul_ago_app,
            compromiso_sep_oct_app,
            avance_sep_oct_app,
            porcentaje_sep_oct_app,
            compromiso_nov_dic_app,
            avance_nov_dic_app,
            porcentaje_nov_dic_app,
            compra_minima_inicial,
            avance_global,
            porcentaje_global,
            acumulado_anticipado,
            porcentaje_anual
        FROM previo
        WHERE """
        
        params = []
        conditions = []
        
        if clave:
            conditions.append("clave = %s")
            params.append(clave)
            
        if nombre_cliente:
            conditions.append("nombre_cliente LIKE %s")
            params.append(f"%{nombre_cliente}%")
        
        query += " AND ".join(conditions)
        
        # Ejecutar consulta
        cursor.execute(query, tuple(params))
        resultados = cursor.fetchall()

        if not resultados:
            return jsonify({'error': 'No se encontraron registros'}), 404

        return jsonify(resultados), 200

    except Exception as e:
        print(f"Error en buscar_previo: {str(e)}")
        return jsonify({'error': 'Error al procesar la solicitud'}), 500
        
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
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
        print(f"Error en obtener_nombres: {str(e)}")
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
        print("=== ERROR EN BACKEND ===")
        print("Error completo:", str(e))
        print("Tipo de error:", type(e).__name__)
        import traceback
        print("Traceback:", traceback.format_exc())
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
        print("=== ERROR EN BACKEND ===")
        print("Error completo:", str(e))
        print("Tipo de error:", type(e).__name__)
        import traceback
        print("Traceback:", traceback.format_exc())
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
    try:
        # 1. Obtener los datos del cliente enviados desde Angular
        data = request.get_json()
        if not data or 'datos_caratula' not in data:
            return jsonify({"error": "No se proporcionaron datos de la carátula"}), 400

        # 2. Reutilizar la lógica para crear el HTML del PDF
        # La función crear_cuerpo_email devuelve un dict con 'html_caratula_pdf'
        htmls = crear_cuerpo_email(data)
        html_para_pdf = htmls['html_caratula_pdf']

        # 3. Generar el PDF en memoria usando WeasyPrint
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
        print(f"Error al generar PDF: {str(e)}")
        return jsonify({"error": f"Error interno al generar el PDF: {str(e)}"}), 500
    
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