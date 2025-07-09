from flask import Blueprint, jsonify, request
from db_conexion import obtener_conexion

clientes_bp = Blueprint('clientes', __name__, url_prefix='')

@clientes_bp.route('/clientes', methods=['GET'])
def obtener_detalles_clientes():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT 
                COALESCE(g.nombre_grupo, c.clave) AS clave,
                c.zona,
                c.nombre_cliente,
                c.nivel,
                n.compromiso_scott,
                n.compromiso_syncros,
                n.compromiso_apparel,
                n.compromiso_vittoria
            FROM clientes c
            JOIN niveles_distribuidor n ON c.nivel = n.nivel
            LEFT JOIN grupo_clientes g ON c.id_grupo = g.id
            ORDER BY clave
        """)
        resultados = cursor.fetchall()
        return jsonify(resultados), 200
    except Exception as e:
        print("Error al obtener los detalles de los clientes:", str(e))
        return jsonify({"error": "Error en la consulta"}), 500
    finally:
        cursor.close()
        conexion.close()

@clientes_bp.route('/clientes/nombres', methods=['GET'])
def obtener_nombres_clientes():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT 
                COALESCE(g.nombre_grupo, c.clave) AS clave,
                c.nombre_cliente
            FROM clientes c
            LEFT JOIN grupo_clientes g ON c.id_grupo = g.id
            ORDER BY c.nombre_cliente
        """)
        resultados = cursor.fetchall()
        return jsonify([
            {"clave": row["clave"], "nombre_cliente": row["nombre_cliente"]}
            for row in resultados
        ]), 200
    except Exception as e:
        print("Error al obtener los nombres de los clientes:", str(e))
        return jsonify({"error": "Error en la consulta"}), 500
    finally:
        cursor.close()
        conexion.close()
        
@clientes_bp.route('/clientes/buscar', methods=['POST'])
def buscar_cliente():
    data = request.get_json()
    valor = data.get('valor')

    if not valor:
        return jsonify({"error": "Falta el valor"}), 400

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        query = """
            SELECT id, clave, zona, nombre_cliente, nivel
            FROM clientes
            WHERE clave = %s OR nombre_cliente = %s
            LIMIT 1
        """
        cursor.execute(query, (valor, valor))
        cliente = cursor.fetchone()

        if cliente:
            return jsonify(cliente), 200
        else:
            return jsonify({"mensaje": "Cliente no encontrado"}), 404
    except Exception as e:
        print("Error al buscar cliente:", str(e))
        return jsonify({"error": "Error al buscar cliente"}), 500
    finally:
        cursor.close()
        conexion.close()

@clientes_bp.route('/clientes/agregar', methods=['POST'])
def agregar_cliente():
    data = request.get_json()

    clave = data.get('clave')
    zona = data.get('zona')
    nombre_cliente = data.get('nombre_cliente')
    nivel = data.get('nivel')

    # Validar que todos los campos estén presentes
    if not all([clave, zona, nombre_cliente, nivel]):
        return jsonify({"error": "Todos los campos son obligatorios"}), 400

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        # Validar que no exista la clave o el nombre ya registrados
        cursor.execute("SELECT id FROM clientes WHERE clave = %s OR nombre_cliente = %s", (clave, nombre_cliente))
        existente = cursor.fetchone()

        if existente:
            return jsonify({"error": "Ya existe un cliente con esa clave o nombre"}), 409

        # Insertar el nuevo cliente
        query = """
            INSERT INTO clientes (clave, zona, nombre_cliente, nivel)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (clave, zona, nombre_cliente, nivel))
        conexion.commit()

        return jsonify({"mensaje": "Cliente agregado exitosamente"}), 201
    except Exception as e:
        print("Error al agregar cliente:", str(e))
        return jsonify({"error": "Error al agregar cliente"}), 500
    finally:
        cursor.close()
        conexion.close()

@clientes_bp.route('/clientes/editar/<int:id_cliente>', methods=['PUT'])
def editar_cliente(id_cliente):
    data = request.get_json()

    clave = data.get('clave')
    zona = data.get('zona')
    nombre_cliente = data.get('nombre_cliente')
    nivel = data.get('nivel')

    if not all([clave, zona, nombre_cliente, nivel]):
        return jsonify({"error": "Todos los campos son obligatorios"}), 400

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        # Verificar que el cliente exista
        cursor.execute("SELECT id FROM clientes WHERE id = %s", (id_cliente,))
        if cursor.fetchone() is None:
            return jsonify({"error": "Cliente no encontrado"}), 404

        # Actualizar
        query = """
            UPDATE clientes
            SET clave = %s,
                zona = %s,
                nombre_cliente = %s,
                nivel = %s
            WHERE id = %s
        """
        cursor.execute(query, (clave, zona, nombre_cliente, nivel, id_cliente))
        conexion.commit()

        return jsonify({"mensaje": "Cliente actualizado exitosamente"}), 200
    except Exception as e:
        print("Error al editar cliente:", str(e))
        return jsonify({"error": "Error al editar cliente"}), 500
    finally:
        cursor.close()
        conexion.close()

@clientes_bp.route('/clientes/eliminar/<int:id_cliente>', methods=['DELETE'])
def eliminar_cliente(id_cliente):
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        cursor.execute("SELECT id FROM clientes WHERE id = %s", (id_cliente,))
        if cursor.fetchone() is None:
            return jsonify({"error": "Cliente no encontrado"}), 404

        cursor.execute("DELETE FROM clientes WHERE id = %s", (id_cliente,))
        conexion.commit()

        return jsonify({"mensaje": "Cliente eliminado correctamente"}), 200
    except Exception as e:
        print("Error al eliminar cliente:", str(e))
        return jsonify({"error": "Error al eliminar cliente"}), 500
    finally:
        cursor.close()
        conexion.close()
