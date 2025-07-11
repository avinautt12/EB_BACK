from flask import Blueprint, jsonify
from db_conexion import obtener_conexion
from flask import request
import mysql.connector
import jwt
import json

SECRET_KEY = "123456"

proyecciones_bp = Blueprint('proyecciones', __name__, url_prefix='')

@proyecciones_bp.route('/proyecciones', methods=['GET'])
def listar_proyecciones():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM proyecciones_ventas ORDER BY id")
        resultados = cursor.fetchall()

        if resultados:
            return jsonify(resultados), 200
        else:
            return jsonify({"mensaje": "No hay proyecciones registradas"}), 404
    except Exception as e:
        print("Error al obtener proyecciones:", str(e))
        return jsonify({"error": "Error al obtener proyecciones"}), 500
    finally:
        cursor.close()
        conexion.close()

@proyecciones_bp.route('/proyecciones-limpias', methods=['GET'])
def listar_proyecciones_limpias():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, clave_factura, clave_6_digitos, clave_odoo, descripcion, 
                   modelo, precio_publico_iva, ean, referencia 
            FROM proyecciones_ventas 
            ORDER BY id
        """)
        resultados = cursor.fetchall()

        return jsonify(resultados), 200 if resultados else 404
    except Exception as e:
        print("Error al obtener proyecciones limpias:", str(e))
        return jsonify({"error": "Error al obtener proyecciones limpias"}), 500
    finally:
        cursor.close()
        conexion.close()

@proyecciones_bp.route('/proyecciones/agregar', methods=['POST'])
def agregar_proyecciones_cliente():
    data = request.get_json()
    auth_header = request.headers.get('Authorization')

    if not auth_header:
        return jsonify({"error": "No se proporcionó token"}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        id_usuario = decoded.get("id")
    except Exception as e:
        print("Error al decodificar token:", str(e))
        return jsonify({"error": "Token inválido"}), 401

    if not id_usuario:
        return jsonify({"error": "No se proporcionó id_usuario en headers"}), 400

    # Esperamos que `data` sea una lista de proyecciones
    if not isinstance(data, list):
        return jsonify({"error": "Se esperaba una lista de proyecciones"}), 400

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        # Obtener el cliente asociado al usuario una sola vez
        cursor.execute("SELECT cliente_id FROM usuarios WHERE id = %s", (id_usuario,))
        cliente = cursor.fetchone()
        if not cliente or not cliente['cliente_id']:
            return jsonify({"error": "Cliente no encontrado para este usuario"}), 404
        id_cliente = cliente['cliente_id']

        # Insertar cada proyección de la lista
        for proyeccion in data:
            id_proyeccion = proyeccion.get('id_proyeccion')
            cantidades = {
                'q1_oct_2025': proyeccion.get('q1_oct_2025', 0),
                'q2_oct_2025': proyeccion.get('q2_oct_2025', 0),
                'q1_nov_2025': proyeccion.get('q1_nov_2025', 0),
                'q2_nov_2025': proyeccion.get('q2_nov_2025', 0),
                'q1_dic_2025': proyeccion.get('q1_dic_2025', 0),
                'q2_dic_2025': proyeccion.get('q2_dic_2025', 0),
            }

            cursor.execute("""
                INSERT INTO proyecciones_cliente (
                    id_cliente, id_proyeccion, q1_oct_2025, q2_oct_2025, q1_nov_2025, q2_nov_2025, q1_dic_2025, q2_dic_2025
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                id_cliente, id_proyeccion,
                cantidades['q1_oct_2025'], cantidades['q2_oct_2025'],
                cantidades['q1_nov_2025'], cantidades['q2_nov_2025'],
                cantidades['q1_dic_2025'], cantidades['q2_dic_2025']
            ))

        conexion.commit()
        return jsonify({"mensaje": "Proyecciones registradas correctamente"}), 201

    except mysql.connector.Error as err:
        print("Error al insertar proyecciones:", str(err))
        conexion.rollback()
        return jsonify({"error": "Error al insertar proyecciones"}), 500
    finally:
        cursor.close()
        conexion.close()

@proyecciones_bp.route('/proyecciones/historial', methods=['GET'])
def historial_proyecciones_cliente():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({"error": "No se proporcionó token"}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        id_usuario = decoded.get("id")
    except Exception as e:
        print("Error al decodificar token:", str(e))
        return jsonify({"error": "Token inválido"}), 401

    try:
        # Buscar el ID del cliente asociado al usuario autenticado
        cursor.execute("SELECT cliente_id FROM usuarios WHERE id = %s", (id_usuario,))
        cliente = cursor.fetchone()

        if not cliente or not cliente['cliente_id']:
            return jsonify({"error": "Cliente no encontrado"}), 404

        id_cliente = cliente['cliente_id']

        # Buscar historial de proyecciones del cliente
        cursor.execute("""
            SELECT 
                pc.*, 
                pv.descripcion, 
                pv.modelo,
                pv.clave_factura,
                pv.precio_publico_iva
            FROM proyecciones_cliente pc
            JOIN proyecciones_ventas pv ON pc.id_proyeccion = pv.id
            WHERE pc.id_cliente = %s
            ORDER BY pc.fecha_registro DESC
        """, (id_cliente,))
        proyecciones = cursor.fetchall()

        if not proyecciones:
            return jsonify({"mensaje": "Este cliente no tiene historial"}), 404

        return jsonify(proyecciones), 200

    except Exception as e:
        print("Error al obtener historial:", str(e))
        return jsonify({"error": "Error al obtener historial"}), 500
    finally:
        cursor.close()
        conexion.close()

@proyecciones_bp.route('/proyecciones/detalles/<int:id_proyeccion>', methods=['GET'])
def detalles_proyeccion(id_proyeccion):
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT 
                pv.id,
                pv.clave_factura,
                pv.clave_6_digitos,
                pv.clave_odoo,
                pv.descripcion,
                pv.modelo,
                pv.precio_publico_iva,
                pv.ean,
                pv.referencia,
                pv.orden_total_cant,
                pv.orden_total_importe,
                pv.q1_oct_2025,
                pv.q2_oct_2025,
                pv.q1_nov_2025,
                pv.q2_nov_2025,
                pv.q1_dic_2025,
                pv.q2_dic_2025,
                -- Historial por cliente
                JSON_ARRAYAGG(JSON_OBJECT(
                    'nombre_cliente', c.nombre_cliente,
                    'fecha_registro', pc.fecha_registro,
                    'q1_oct_2025', pc.q1_oct_2025,
                    'q2_oct_2025', pc.q2_oct_2025,
                    'q1_nov_2025', pc.q1_nov_2025,
                    'q2_nov_2025', pc.q2_nov_2025,
                    'q1_dic_2025', pc.q1_dic_2025,
                    'q2_dic_2025', pc.q2_dic_2025
                )) AS historial_clientes

            FROM proyecciones_ventas pv
            LEFT JOIN proyecciones_cliente pc ON pv.id = pc.id_proyeccion
            LEFT JOIN clientes c ON pc.id_cliente = c.id
            WHERE pv.id = %s
            GROUP BY pv.id
        """, (id_proyeccion,))
        
        resultado = cursor.fetchone()
        if not resultado:
            return jsonify({"mensaje": "Proyección no encontrada"}), 404

        if resultado.get("historial_clientes"):
            try:
                resultado["historial_clientes"] = json.loads(resultado["historial_clientes"])
            except Exception as e:
                print("Error al parsear historial_clientes:", str(e))
                resultado["historial_clientes"] = []

        return jsonify(resultado), 200

    except Exception as e:
        print("Error al obtener detalles de proyección:", str(e))
        return jsonify({"error": "Error al obtener detalles de proyección"}), 500
    finally:
        cursor.close()
        conexion.close()


