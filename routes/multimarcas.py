from flask import Blueprint, jsonify, request
from db_conexion import obtener_conexion
from decimal import Decimal

multimarcas_bp = Blueprint('multimarcas', __name__, url_prefix='')

@multimarcas_bp.route('/actualizar_multimarcas', methods=['POST'])
def actualizar_multimarcas():
    conexion = None
    cursor = None
    
    try:
        # Verificar que se recibió data JSON
        if not request.is_json:
            return jsonify({'error': 'Se esperaba un JSON en el cuerpo de la solicitud'}), 400
        
        data = request.get_json()
        
        # El frontend envía { datos: [...] } o directamente la lista
        registros = data.get('datos', data) if isinstance(data, dict) else data
        
        # Validar estructura de los datos
        if not isinstance(registros, list):
            return jsonify({'error': 'Los datos deben ser una lista de registros'}), 400
            
        if len(registros) == 0:
            return jsonify({'error': 'No se recibieron registros para actualizar'}), 400
        
        print(f"Recibidos {len(registros)} registros para actualizar en multimarcas")
        
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        
        # 1. Limpiar la tabla existente
        cursor.execute("TRUNCATE TABLE multimarcas")
        
        # 2. Insertar los nuevos registros
        registros_insertados = 0
        
        for registro in registros:
            try:
                # Validar campos mínimos requeridos
                if not all(key in registro for key in ['clave', 'evac', 'cliente_razon_social']):
                    print(f"Registro omitido: falta clave, evac o cliente_razon_social")
                    continue
                
                # Calcular avance_global si no viene en los datos
                avance_global = registro.get('avance_global') or sum(
                    Decimal(registro.get(field, 0) or 0)
                    for field in [
                        'avance_global_scott',
                        'avance_global_syncros',
                        'avance_global_apparel',
                        'avance_global_vittoria',
                        'avance_global_bold'
                    ]
                )
                
                cursor.execute("""
                    INSERT INTO multimarcas (
                        clave, evac, cliente_razon_social, avance_global,
                        avance_global_scott, avance_global_syncros, avance_global_apparel,
                        avance_global_vittoria, avance_global_bold,
                        total_facturas_julio, total_facturas_agosto, total_facturas_septiembre,
                        total_facturas_octubre, total_facturas_noviembre, total_facturas_diciembre,
                        total_facturas_enero, total_facturas_febrero, total_facturas_marzo,
                        total_facturas_abril, total_facturas_mayo, total_facturas_junio
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    registro['clave'],
                    registro['evac'],
                    registro['cliente_razon_social'],
                    avance_global,
                    registro.get('avance_global_scott', 0),
                    registro.get('avance_global_syncros', 0),
                    registro.get('avance_global_apparel', 0),
                    registro.get('avance_global_vittoria', 0),
                    registro.get('avance_global_bold', 0),
                    registro.get('total_facturas_julio', 0),
                    registro.get('total_facturas_agosto', 0),
                    registro.get('total_facturas_septiembre', 0),
                    registro.get('total_facturas_octubre', 0),
                    registro.get('total_facturas_noviembre', 0),
                    registro.get('total_facturas_diciembre', 0),
                    registro.get('total_facturas_enero', 0),
                    registro.get('total_facturas_febrero', 0),
                    registro.get('total_facturas_marzo', 0),
                    registro.get('total_facturas_abril', 0),
                    registro.get('total_facturas_mayo', 0),
                    registro.get('total_facturas_junio', 0)
                ))
                
                registros_insertados += 1
                
            except Exception as insert_error:
                print(f"Error insertando registro (clave: {registro.get('clave', 'N/A')}): {insert_error}")
                continue
        
        conexion.commit()
        return jsonify({
            'mensaje': f'Datos de multimarcas actualizados. {registros_insertados}/{len(registros)} registros insertados.',
            'success': True
        }), 200
    
    except Exception as e:
        print(f"Error general: {str(e)}")
        if conexion:
            conexion.rollback()
        return jsonify({'error': str(e), 'success': False}), 500
    
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@multimarcas_bp.route('/obtener_multimarcas', methods=['GET'])
def obtener_multimarcas():
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT * FROM multimarcas")
        resultados = cursor.fetchall()
        return jsonify(resultados), 200
    except Exception as e:
        print(f"Error al obtener multimarcas: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@multimarcas_bp.route('/agregar_cliente', methods=['POST'])
def agregar_cliente():
    conexion = None
    cursor = None
    try:
        datos = request.get_json()
        clave = datos.get('clave')
        evac = datos.get('evac')
        cliente_razon_social = datos.get('cliente_razon_social')

        if not clave:
            return jsonify({'error': 'El campo clave es obligatorio'}), 400

        conexion = obtener_conexion()
        cursor = conexion.cursor()

        # Verificar si el cliente ya existe
        cursor.execute("SELECT id FROM clientes_multimarcas WHERE clave = %s", (clave,))
        if cursor.fetchone():
            return jsonify({'error': 'Ya existe un cliente con esta clave'}), 400

        # Insertar nuevo cliente
        cursor.execute(
            "INSERT INTO clientes_multimarcas (clave, evac, cliente_razon_social) VALUES (%s, %s, %s)",
            (clave, evac, cliente_razon_social)
        )
        conexion.commit()

        return jsonify({
            'mensaje': 'Cliente agregado correctamente',
            'id': cursor.lastrowid
        }), 201

    except Exception as e:
        if conexion:
            conexion.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@multimarcas_bp.route('/editar_cliente/<int:id>', methods=['PUT'])
def editar_cliente(id):
    conexion = None
    cursor = None
    try:
        datos = request.get_json()
        clave = datos.get('clave')
        evac = datos.get('evac')
        cliente_razon_social = datos.get('cliente_razon_social')

        if not clave:
            return jsonify({'error': 'El campo clave es obligatorio'}), 400

        conexion = obtener_conexion()
        cursor = conexion.cursor()

        # Verificar si el cliente existe
        cursor.execute("SELECT id FROM clientes_multimarcas WHERE id = %s", (id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Cliente no encontrado'}), 404

        # Verificar si la nueva clave ya está en uso por otro cliente
        cursor.execute(
            "SELECT id FROM clientes_multimarcas WHERE clave = %s AND id != %s", 
            (clave, id)
        )
        if cursor.fetchone():
            return jsonify({'error': 'La clave ya está en uso por otro cliente'}), 400

        # Actualizar cliente
        cursor.execute(
            """UPDATE clientes_multimarcas 
            SET clave = %s, evac = %s, cliente_razon_social = %s 
            WHERE id = %s""",
            (clave, evac, cliente_razon_social, id)
        )
        conexion.commit()

        return jsonify({'mensaje': 'Cliente actualizado correctamente'}), 200

    except Exception as e:
        if conexion:
            conexion.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@multimarcas_bp.route('/eliminar_cliente/<int:id>', methods=['DELETE'])
def eliminar_cliente(id):
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        # Verificar si el cliente existe
        cursor.execute("SELECT id FROM clientes_multimarcas WHERE id = %s", (id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Cliente no encontrado'}), 404

        # Eliminar cliente
        cursor.execute("DELETE FROM clientes_multimarcas WHERE id = %s", (id,))
        conexion.commit()

        return jsonify({'mensaje': 'Cliente eliminado correctamente'}), 200

    except Exception as e:
        if conexion:
            conexion.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()