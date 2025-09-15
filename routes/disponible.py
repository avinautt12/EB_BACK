from flask import Blueprint, request, jsonify
from db_conexion import obtener_conexion

disponibilidad_bp = Blueprint('disponibilidad', __name__, url_prefix='')

@disponibilidad_bp.route('/disponibilidades', methods=['GET'])
def listar_disponibilidades():
    """Obtiene todas las disponibilidades con sus descripciones"""
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, 
                   q1_oct_2025, q2_oct_2025, 
                   q1_nov_2025, q2_nov_2025,
                   q1_dic_2025, q2_dic_2025,
                   descripcion
            FROM disponibilidad_proyeccion 
            ORDER BY id
        """)
        resultados = cursor.fetchall()
        
        return jsonify({
            "success": True,
            "data": resultados,
            "count": len(resultados)
        }), 200
    except Exception as e:
        print("Error al obtener disponibilidades:", str(e))
        return jsonify({
            "success": False,
            "error": "Error al obtener disponibilidades",
            "details": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@disponibilidad_bp.route('/disponibilidades/agregar', methods=['POST'])
def agregar_disponibilidad():
    """Agrega una nueva disponibilidad"""
    data = request.get_json()
    
    # Validación de campos
    campos_requeridos = {
        'q1_oct_2025': bool,
        'q2_oct_2025': bool,
        'q1_nov_2025': bool,
        'q2_nov_2025': bool,
        'q1_dic_2025': bool,
        'q2_dic_2025': bool,
        'descripcion': str
    }
    
    errors = []
    for campo, tipo in campos_requeridos.items():
        if campo not in data:
            errors.append(f"Campo requerido faltante: {campo}")
        elif not isinstance(data[campo], tipo):
            errors.append(f"Tipo incorrecto para {campo}. Se esperaba {tipo.__name__}")
    
    if errors:
        return jsonify({
            "success": False,
            "errors": errors
        }), 400

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        cursor.execute("""
            INSERT INTO disponibilidad_proyeccion (
                q1_oct_2025, q2_oct_2025, 
                q1_nov_2025, q2_nov_2025,
                q1_dic_2025, q2_dic_2025,
                descripcion
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            data['q1_oct_2025'], data['q2_oct_2025'],
            data['q1_nov_2025'], data['q2_nov_2025'],
            data['q1_dic_2025'], data['q2_dic_2025'],
            data['descripcion']
        ))
        conexion.commit()
        
        nuevo_id = cursor.lastrowid
        
        # Obtener el registro recién creado
        cursor.execute("SELECT * FROM disponibilidad_proyeccion WHERE id = %s", (nuevo_id,))
        nueva_disponibilidad = cursor.fetchone()
        
        return jsonify({
            "success": True,
            "message": "Disponibilidad agregada correctamente",
            "data": nueva_disponibilidad
        }), 201
    except Exception as e:
        print("Error al agregar disponibilidad:", str(e))
        conexion.rollback()
        return jsonify({
            "success": False,
            "error": "Error al agregar disponibilidad",
            "details": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@disponibilidad_bp.route('/disponibilidades/<int:id>', methods=['GET'])
def obtener_disponibilidad(id):
    """Obtiene una disponibilidad específica por su ID"""
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, 
                   q1_oct_2025, q2_oct_2025, 
                   q1_nov_2025, q2_nov_2025,
                   q1_dic_2025, q2_dic_2025,
                   descripcion
            FROM disponibilidad_proyeccion 
            WHERE id = %s
        """, (id,))
        disponibilidad = cursor.fetchone()
        
        if not disponibilidad:
            return jsonify({
                "success": False,
                "error": "Disponibilidad no encontrada"
            }), 404
        
        return jsonify({
            "success": True,
            "data": disponibilidad
        }), 200
    except Exception as e:
        print("Error al obtener disponibilidad:", str(e))
        return jsonify({
            "success": False,
            "error": "Error al obtener disponibilidad",
            "details": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@disponibilidad_bp.route('/disponibilidades/editar/<int:id>', methods=['PUT'])
def editar_disponibilidad(id):
    """Actualiza una disponibilidad existente"""
    data = request.get_json()
    
    # Validación de campos
    campos_requeridos = {
        'q1_oct_2025': bool,
        'q2_oct_2025': bool,
        'q1_nov_2025': bool,
        'q2_nov_2025': bool,
        'q1_dic_2025': bool,
        'q2_dic_2025': bool,
        'descripcion': str
    }
    
    errors = []
    for campo, tipo in campos_requeridos.items():
        if campo not in data:
            errors.append(f"Campo requerido faltante: {campo}")
        elif not isinstance(data[campo], tipo):
            errors.append(f"Tipo incorrecto para {campo}. Se esperaba {tipo.__name__}")
    
    if errors:
        return jsonify({
            "success": False,
            "errors": errors
        }), 400

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        # Verificar existencia
        cursor.execute("SELECT id FROM disponibilidad_proyeccion WHERE id = %s", (id,))
        if not cursor.fetchone():
            return jsonify({
                "success": False,
                "error": "Disponibilidad no encontrada"
            }), 404
        
        cursor.execute("""
            UPDATE disponibilidad_proyeccion SET
                q1_oct_2025 = %s,
                q2_oct_2025 = %s,
                q1_nov_2025 = %s,
                q2_nov_2025 = %s,
                q1_dic_2025 = %s,
                q2_dic_2025 = %s,
                descripcion = %s
            WHERE id = %s
        """, (
            data['q1_oct_2025'], data['q2_oct_2025'],
            data['q1_nov_2025'], data['q2_nov_2025'],
            data['q1_dic_2025'], data['q2_dic_2025'],
            data['descripcion'],
            id
        ))
        conexion.commit()
        
        # Obtener el registro actualizado
        cursor.execute("SELECT * FROM disponibilidad_proyeccion WHERE id = %s", (id,))
        disponibilidad_actualizada = cursor.fetchone()
        
        return jsonify({
            "success": True,
            "message": "Disponibilidad actualizada correctamente",
            "data": disponibilidad_actualizada
        }), 200
    except Exception as e:
        print("Error al editar disponibilidad:", str(e))
        conexion.rollback()
        return jsonify({
            "success": False,
            "error": "Error al editar disponibilidad",
            "details": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@disponibilidad_bp.route('/disponibilidades/eliminar/<int:id>', methods=['DELETE'])
def eliminar_disponibilidad(id):
    """Elimina una disponibilidad existente"""
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        # Verificar existencia
        cursor.execute("SELECT id FROM disponibilidad_proyeccion WHERE id = %s", (id,))
        if not cursor.fetchone():
            return jsonify({
                "success": False,
                "error": "Disponibilidad no encontrada"
            }), 404

        cursor.execute("DELETE FROM disponibilidad_proyeccion WHERE id = %s", (id,))
        conexion.commit()
        
        return jsonify({
            "success": True,
            "message": "Disponibilidad eliminada correctamente"
        }), 200
    except Exception as e:
        print("Error al eliminar disponibilidad:", str(e))
        conexion.rollback()
        return jsonify({
            "success": False,
            "error": "Error al eliminar disponibilidad",
            "details": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()