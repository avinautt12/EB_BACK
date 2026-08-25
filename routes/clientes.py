from flask import Blueprint, jsonify, request
from db_conexion import obtener_conexion
import jwt
from datetime import date, datetime

from utils.jwt_utils import verificar_token
from functools import wraps


SECRET_KEY = "123456"

clientes_bp = Blueprint('clientes', __name__, url_prefix='')


# ============================================================
# OBTENER TODOS LOS CLIENTES ACTIVOS
# ============================================================
@clientes_bp.route('/clientes', methods=['GET'])
def obtener_detalles_clientes():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT 
                c.clave,
                c.evac,
                c.nombre_cliente,
                c.nivel,
                c.f_inicio,
                c.f_fin
            FROM clientes c
            WHERE c.activo = 1
              AND c.nombre_cliente NOT IN (
                  'Alberto Garcia',
                  'Andre Padilla Goray',
                  'Andre Vittoria'
              )
            ORDER BY 
                CASE 
                    WHEN c.evac = 'A' THEN 1
                    WHEN c.evac = 'B' THEN 2
                    WHEN c.evac = 'GO' THEN 3
                    ELSE 4
                END,
                c.nombre_cliente ASC
        """)

        resultados = cursor.fetchall()

        # Convertir objetos date/datetime a strings
        for cliente in resultados:
            if cliente['f_inicio'] and isinstance(
                cliente['f_inicio'], (datetime, date)
            ):
                cliente['f_inicio'] = cliente['f_inicio'].strftime('%Y-%m-%d')

            if cliente['f_fin'] and isinstance(
                cliente['f_fin'], (datetime, date)
            ):
                cliente['f_fin'] = cliente['f_fin'].strftime('%Y-%m-%d')

        return jsonify(resultados), 200

    except Exception as e:
        print("Error al obtener los detalles de los clientes:", str(e))
        return jsonify({"error": "Error en la consulta"}), 500

    finally:
        if cursor:
            cursor.close()

        if conexion and conexion.is_connected():
            conexion.close()


# ============================================================
# OBTENER NOMBRES DE CLIENTES ACTIVOS
# ============================================================
@clientes_bp.route('/clientes/nombres', methods=['GET'])
def obtener_nombres_clientes():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT 
                c.id,
                COALESCE(g.nombre_grupo, c.clave) AS clave,
                c.nombre_cliente
            FROM clientes c
            LEFT JOIN grupo_clientes g
                ON c.id_grupo = g.id
            WHERE c.activo = 1
            ORDER BY c.nombre_cliente
        """)

        resultados = cursor.fetchall()

        return jsonify([
            {
                "id": row["id"],
                "clave": row["clave"],
                "nombre_cliente": row["nombre_cliente"]
            }
            for row in resultados
        ]), 200

    except Exception as e:
        print("Error al obtener los nombres de los clientes:", str(e))
        return jsonify({"error": "Error en la consulta"}), 500

    finally:
        if cursor:
            cursor.close()

        if conexion and conexion.is_connected():
            conexion.close()


# ============================================================
# CLIENTES ACTIVOS POR GRUPO
# ============================================================
@clientes_bp.route('/clientes/por-grupo/<int:id_grupo>', methods=['GET'])
def obtener_clientes_por_grupo(id_grupo):
    """
    Devuelve los clientes activos que pertenecen
    a un grupo integral específico.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                c.id,
                c.clave,
                c.nombre_cliente
            FROM clientes c
            WHERE c.id_grupo = %s
              AND c.activo = 1
            ORDER BY c.nombre_cliente
        """, (id_grupo,))

        resultados = cursor.fetchall()

        return jsonify(resultados), 200

    except Exception as e:
        print("Error al obtener clientes por grupo:", str(e))
        return jsonify({"error": "Error en la consulta"}), 500

    finally:
        if cursor:
            cursor.close()

        if conexion and conexion.is_connected():
            conexion.close()


# ============================================================
# BUSCAR CLIENTE ACTIVO
# ============================================================
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
            SELECT
                id,
                clave,
                evac,
                nombre_cliente,
                nivel,
                f_inicio,
                f_fin
            FROM clientes
            WHERE activo = 1
              AND (
                    clave = %s
                    OR nombre_cliente = %s
              )
            LIMIT 1
        """

        cursor.execute(query, (valor, valor))

        cliente = cursor.fetchone()

        if cliente:
            return jsonify(cliente), 200

        return jsonify({
            "mensaje": "Cliente no encontrado"
        }), 404

    except Exception as e:
        print("Error al buscar cliente:", str(e))
        return jsonify({
            "error": "Error al buscar cliente"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if conexion and conexion.is_connected():
            conexion.close()


# ============================================================
# AGREGAR CLIENTE
# ============================================================
@clientes_bp.route('/clientes/agregar', methods=['POST'])
def agregar_cliente():
    data = request.get_json()

    clave = (data.get('clave') or '').strip()
    evac = (data.get('evac') or '').strip()
    nombre_cliente = (data.get('nombre_cliente') or '').strip()
    nivel = (data.get('nivel') or '').strip()
    f_inicio = data.get('f_inicio')
    f_fin = data.get('f_fin')

    if not all([
        clave,
        evac,
        nombre_cliente,
        nivel,
        f_inicio,
        f_fin
    ]):
        return jsonify({
            "error": "Todos los campos son obligatorios"
        }), 400

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        # ====================================================
        # VALIDAR DUPLICADO
        # ====================================================
        cursor.execute("""
            SELECT
                id,
                clave,
                nombre_cliente,
                nivel,
                activo
            FROM clientes
            WHERE clave = %s
               OR nombre_cliente = %s
            LIMIT 1
        """, (
            clave,
            nombre_cliente
        ))

        existente = cursor.fetchone()

        if existente:
            # Si existe pero está inactivo, indicarlo
            if existente.get('activo') == 0:
                return jsonify({
                    "error": (
                        "El cliente ya existe pero se encuentra inactivo"
                    ),
                    "existente": existente
                }), 409

            return jsonify({
                "error": (
                    "Ya existe un cliente con esa clave o nombre"
                ),
                "existente": existente
            }), 409

        # ====================================================
        # INSERTAR NUEVO CLIENTE
        # activo se queda en 1 por DEFAULT de MySQL
        # ====================================================
        query = """
            INSERT INTO clientes (
                clave,
                evac,
                nombre_cliente,
                nivel,
                f_inicio,
                f_fin
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (
                clave,
                evac,
                nombre_cliente,
                nivel,
                f_inicio,
                f_fin
            )
        )

        conexion.commit()

        nuevo_id = cursor.lastrowid

        return jsonify({
            "mensaje": "Cliente agregado exitosamente",
            "id": nuevo_id
        }), 201

    except Exception as e:
        conexion.rollback()

        print("Error al agregar cliente:", str(e))

        return jsonify({
            "error": "Error al agregar cliente",
            "detalle": str(e)
        }), 500

    finally:
        if cursor:
            cursor.close()

        if conexion and conexion.is_connected():
            conexion.close()


# ============================================================
# EDITAR CLIENTE
# ============================================================
@clientes_bp.route('/clientes/editar/<int:id_cliente>', methods=['PUT'])
def editar_cliente(id_cliente):
    data = request.get_json()

    clave = (data.get('clave') or '').strip()
    evac = (data.get('evac') or '').strip()
    nombre_cliente = (data.get('nombre_cliente') or '').strip()
    nivel = (data.get('nivel') or '').strip()
    f_inicio = data.get('f_inicio')
    f_fin = data.get('f_fin')

    if not all([
        clave,
        evac,
        nombre_cliente,
        nivel,
        f_inicio,
        f_fin
    ]):
        return jsonify({
            "error": "Todos los campos son obligatorios"
        }), 400

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        # Verificar que el cliente exista
        cursor.execute("""
            SELECT id, activo
            FROM clientes
            WHERE id = %s
        """, (id_cliente,))

        cliente = cursor.fetchone()

        if cliente is None:
            return jsonify({
                "error": "Cliente no encontrado"
            }), 404

        if cliente['activo'] == 0:
            return jsonify({
                "error": "No se puede editar un cliente inactivo"
            }), 409

        # Validar duplicados excluyendo el cliente actual
        cursor.execute("""
            SELECT id
            FROM clientes
            WHERE (
                    clave = %s
                    OR nombre_cliente = %s
                  )
              AND id <> %s
            LIMIT 1
        """, (
            clave,
            nombre_cliente,
            id_cliente
        ))

        duplicado = cursor.fetchone()

        if duplicado:
            return jsonify({
                "error": (
                    "Ya existe otro cliente con esa clave o nombre"
                )
            }), 409

        # Actualizar cliente
        query = """
            UPDATE clientes
            SET
                clave = %s,
                evac = %s,
                nombre_cliente = %s,
                nivel = %s,
                f_inicio = %s,
                f_fin = %s
            WHERE id = %s
        """

        cursor.execute(
            query,
            (
                clave,
                evac,
                nombre_cliente,
                nivel,
                f_inicio,
                f_fin,
                id_cliente
            )
        )

        conexion.commit()

        return jsonify({
            "mensaje": "Cliente actualizado exitosamente"
        }), 200

    except Exception as e:
        conexion.rollback()

        print("Error al editar cliente:", str(e))

        return jsonify({
            "error": "Error al editar cliente"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if conexion and conexion.is_connected():
            conexion.close()


# ============================================================
# DESACTIVAR CLIENTE
#
# IMPORTANTE:
# Ya NO elimina físicamente el registro.
# Mantiene historial y relaciones.
# ============================================================
@clientes_bp.route('/clientes/eliminar/<int:id_cliente>', methods=['DELETE'])
def eliminar_cliente(id_cliente):
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                id,
                clave,
                nombre_cliente,
                activo
            FROM clientes
            WHERE id = %s
        """, (id_cliente,))

        cliente = cursor.fetchone()

        if cliente is None:
            return jsonify({
                "error": "Cliente no encontrado"
            }), 404

        if cliente['activo'] == 0:
            return jsonify({
                "error": "El cliente ya se encuentra inactivo"
            }), 409

        cursor.execute("""
            UPDATE clientes
            SET activo = 0
            WHERE id = %s
        """, (id_cliente,))

        conexion.commit()

        return jsonify({
            "mensaje": "Cliente desactivado correctamente",
            "cliente": {
                "id": cliente["id"],
                "clave": cliente["clave"],
                "nombre_cliente": cliente["nombre_cliente"]
            }
        }), 200

    except Exception as e:
        conexion.rollback()

        print("Error al desactivar cliente:", str(e))

        return jsonify({
            "error": "Error al desactivar cliente"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if conexion and conexion.is_connected():
            conexion.close()


# ============================================================
# OBTENER NIVEL DEL CLIENTE ACTUAL
# ============================================================
@clientes_bp.route('/clientes/nivel', methods=['GET'])
def obtener_nivel_cliente_actual():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({
            "error": "Token no proporcionado"
        }), 401

    token = auth_header.split(' ')[1]

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=['HS256']
        )

        usuario_id = payload['id']

    except jwt.ExpiredSignatureError:
        return jsonify({
            "error": "Token expirado"
        }), 401

    except jwt.InvalidTokenError:
        return jsonify({
            "error": "Token inválido"
        }), 401

    try:
        # Obtener cliente_id del usuario
        cursor.execute("""
            SELECT cliente_id
            FROM usuarios
            WHERE id = %s
        """, (usuario_id,))

        usuario = cursor.fetchone()

        if not usuario or not usuario['cliente_id']:
            return jsonify({
                "error": "El usuario no tiene cliente asociado"
            }), 404

        cliente_id = usuario['cliente_id']

        # Obtener nivel y compromiso solo si está activo
        cursor.execute("""
            SELECT
                c.nivel,
                n.compromiso_scott
            FROM clientes c
            JOIN niveles_distribuidor n
                ON c.nivel = n.nivel
            WHERE c.id = %s
              AND c.activo = 1
        """, (cliente_id,))

        cliente = cursor.fetchone()

        if not cliente:
            return jsonify({
                "error": "Cliente no encontrado o inactivo"
            }), 404

        return jsonify({
            "nivel": cliente['nivel'],
            "compromiso": cliente['compromiso_scott']
        }), 200

    except Exception as e:
        print(
            "Error al obtener nivel del cliente:",
            str(e)
        )

        return jsonify({
            "error": "Error en la consulta"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if conexion and conexion.is_connected():
            conexion.close()


# ============================================================
# INFORMACIÓN DEL CLIENTE ACTUAL
# ============================================================
@clientes_bp.route('/clientes/info', methods=['GET'])
def obtener_info_cliente_actual():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({
            "error": "Token no proporcionado"
        }), 401

    token = auth_header.split(' ')[1]

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=['HS256']
        )

        usuario_id = payload['id']

    except jwt.ExpiredSignatureError:
        return jsonify({
            "error": "Token expirado"
        }), 401

    except jwt.InvalidTokenError:
        return jsonify({
            "error": "Token inválido"
        }), 401

    try:
        # Obtener cliente_id del usuario
        cursor.execute("""
            SELECT cliente_id
            FROM usuarios
            WHERE id = %s
        """, (usuario_id,))

        usuario = cursor.fetchone()

        if not usuario or not usuario['cliente_id']:
            return jsonify({
                "error": "El usuario no tiene cliente asociado"
            }), 404

        cliente_id = usuario['cliente_id']

        # Obtener información del cliente
        # únicamente si está activo
        cursor.execute("""
            SELECT
                id,
                clave,
                zona,
                nombre_cliente,
                nivel,
                id_grupo
            FROM clientes
            WHERE id = %s
              AND activo = 1
        """, (cliente_id,))

        cliente = cursor.fetchone()

        if not cliente:
            return jsonify({
                "error": "Cliente no encontrado o inactivo"
            }), 404

        return jsonify(cliente), 200

    except Exception as e:
        print(
            "Error al obtener la información del cliente:",
            str(e)
        )

        return jsonify({
            "error": "Error en la consulta"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if conexion and conexion.is_connected():
            conexion.close()


# ============================================================
# CLIENTES MULTIMARCAS ACTIVOS
# ============================================================
@clientes_bp.route('/clientes_multimarcas', methods=['GET'])
def obtener_clientes_multimarcas():
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                id,
                clave,
                evac,
                cliente_razon_social,
                activo
            FROM clientes_multimarcas
            WHERE activo = 1
            ORDER BY
                CASE
                    WHEN evac = 'A' THEN 1
                    WHEN evac = 'B' THEN 2
                    ELSE 3
                END,
                cliente_razon_social ASC
        """)

        resultados = cursor.fetchall()

        return jsonify(resultados), 200

    except Exception as e:
        print(
            "Error al obtener clientes multimarcas:",
            str(e)
        )

        return jsonify({
            "error": "Error en la consulta"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if conexion and conexion.is_connected():
            conexion.close()


# ============================================================
# CLAVES CLIENTES MULTIMARCAS ACTIVOS
# ============================================================
@clientes_bp.route('/clientes_multimarcas_claves', methods=['GET'])
def obtener_clientes_multimarcas_claves():
    conexion = None
    cursor = None

    clave = (request.args.get('clave') or '').strip()

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)

        if clave:
            cursor.execute("""
                SELECT
                    id,
                    clave,
                    evac,
                    cliente_razon_social,
                    activo
                FROM clientes_multimarcas
                WHERE clave = %s
                  AND activo = 1
                ORDER BY id
                LIMIT 1
            """, (clave,))

            resultado = cursor.fetchone()

            if resultado:
                return jsonify(resultado), 200

            return jsonify({
                "error": "Cliente no encontrado o inactivo"
            }), 404

        cursor.execute("""
            SELECT
                id,
                clave,
                evac,
                cliente_razon_social,
                activo
            FROM clientes_multimarcas
            WHERE activo = 1
            ORDER BY
                CASE
                    WHEN evac = 'A' THEN 1
                    WHEN evac = 'B' THEN 2
                    ELSE 3
                END,
                cliente_razon_social ASC
        """)

        return jsonify(cursor.fetchall()), 200

    except Exception as e:
        print(
            "Error al obtener clientes multimarcas:",
            str(e)
        )

        return jsonify({
            "error": "Error en la consulta"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if conexion and conexion.is_connected():
            conexion.close()


# ============================================================
# BUSCAR CLIENTE MULTIMARCAS ACTIVO
# ============================================================
@clientes_bp.route('/clientes_multimarcas_buscar', methods=['GET'])
def buscar_cliente_multimarcas():
    conexion = None
    cursor = None

    busqueda = (request.args.get('q') or '').strip()

    if not busqueda:
        return jsonify({
            "error": "Parámetro de búsqueda requerido"
        }), 400

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)

        parametro_busqueda = f"%{busqueda}%"

        query = """
            SELECT
                id,
                clave,
                cliente_razon_social,
                evac,
                activo
            FROM clientes_multimarcas
            WHERE activo = 1
              AND (
                    clave LIKE %s
                    OR cliente_razon_social LIKE %s
              )
            ORDER BY
                CASE
                    WHEN evac = 'A' THEN 1
                    WHEN evac = 'B' THEN 2
                    ELSE 3
                END,
                cliente_razon_social ASC
        """

        cursor.execute(
            query,
            (
                parametro_busqueda,
                parametro_busqueda
            )
        )

        resultados = cursor.fetchall()

        return jsonify(resultados), 200

    except Exception as e:
        print("Error al buscar cliente:", str(e))

        return jsonify({
            "error": "Error en la consulta"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if conexion and conexion.is_connected():
            conexion.close()


# ============================================================
# OBTENER FECHAS DE CLIENTES ACTIVOS
# ============================================================
@clientes_bp.route('/clientes_fechas', methods=['GET'])
def obtener_fechas_clientes():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT 
                c.nombre_cliente,
                c.f_inicio,
                c.f_fin
            FROM clientes c
            WHERE c.activo = 1
              AND c.nombre_cliente NOT IN (
                  'Alberto Garcia',
                  'Andre Padilla Goray',
                  'Andre Vittoria'
              )
            ORDER BY
                c.nombre_cliente ASC
        """)

        resultados = cursor.fetchall()

        for cliente in resultados:
            if cliente['f_inicio'] and isinstance(
                cliente['f_inicio'], (datetime, date)
            ):
                cliente['f_inicio'] = cliente[
                    'f_inicio'
                ].strftime('%Y-%m-%d')

            if cliente['f_fin'] and isinstance(
                cliente['f_fin'], (datetime, date)
            ):
                cliente['f_fin'] = cliente[
                    'f_fin'
                ].strftime('%Y-%m-%d')

        return jsonify(resultados), 200

    except Exception as e:
        print(
            "Error al obtener las fechas de los clientes:",
            str(e)
        )

        return jsonify({
            "error": "Error en la consulta"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if conexion and conexion.is_connected():
            conexion.close()


# ============================================================
# DECORADOR TOKEN
# ============================================================
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({
                'error': 'Token es requerido'
            }), 401

        try:
            # Remover "Bearer " si está presente
            if token.startswith('Bearer '):
                token = token[7:]

            decoded_token = verificar_token(token)

            if not decoded_token:
                return jsonify({
                    'error': 'Token inválido o expirado'
                }), 401

            request.cliente_data = decoded_token

        except Exception as e:
            print(
                "Error al procesar token:",
                str(e)
            )

            return jsonify({
                'error': 'Error al procesar token'
            }), 401

        return f(*args, **kwargs)

    return decorated


# ============================================================
# FACTURAS DEL CLIENTE
# ============================================================
@clientes_bp.route('/facturas-cliente', methods=['GET'])
@token_required
def obtener_facturas_cliente():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        cliente_data = getattr(
            request,
            'cliente_data',
            None
        )

        if not cliente_data:
            return jsonify({
                "error": "Datos del cliente no encontrados"
            }), 400

        clave_cliente = cliente_data.get('clave')
        nombre_cliente = cliente_data.get(
            'nombre_cliente'
        )

        if not clave_cliente and not nombre_cliente:
            return jsonify({
                "error": (
                    "No se encontró información del "
                    "cliente en el token"
                )
            }), 400

        # Validar que el cliente siga activo
        cursor.execute("""
            SELECT
                f_inicio
            FROM clientes
            WHERE clave = %s
              AND activo = 1
        """, (clave_cliente,))

        cliente_info = cursor.fetchone()

        if not cliente_info:
            return jsonify({
                "error": "Cliente no encontrado o inactivo"
            }), 404

        if not cliente_info['f_inicio']:
            return jsonify({
                "success": True,
                "mensaje": (
                    "El cliente no tiene una fecha de inicio "
                    "de temporada configurada."
                ),
                "data": []
            }), 200

        fecha_inicio_temporada = cliente_info[
            'f_inicio'
        ]

        query = """
            SELECT 
                id,
                numero_factura,
                referencia_interna,
                nombre_producto,
                contacto_referencia,
                contacto_nombre,
                fecha_factura,
                precio_unitario,
                cantidad,
                venta_total,
                marca,
                subcategoria,
                apparel,
                eride,
                evac,
                categoria_producto,
                estado_factura
            FROM monitor
            WHERE (
                    contacto_referencia = %s
                    OR contacto_nombre = %s
                  )
              AND fecha_factura >= %s
              AND numero_factura IS NOT NULL
              AND numero_factura != '/'
              AND fecha_factura IS NOT NULL
              AND fecha_factura != '0001-01-01 00:00:00'
            ORDER BY
                CASE
                    WHEN contacto_referencia = %s THEN 1
                    WHEN contacto_nombre = %s THEN 2
                    ELSE 3
                END,
                fecha_factura DESC
        """

        cursor.execute(
            query,
            (
                clave_cliente,
                nombre_cliente,
                fecha_inicio_temporada,
                clave_cliente,
                nombre_cliente
            )
        )

        facturas = cursor.fetchall()

        for factura in facturas:
            if factura['fecha_factura'] and isinstance(
                factura['fecha_factura'],
                (datetime, date)
            ):
                factura['fecha_factura'] = factura[
                    'fecha_factura'
                ].strftime('%Y-%m-%d %H:%M:%S')

        return jsonify({
            "success": True,
            "cliente": {
                "clave": clave_cliente,
                "nombre": nombre_cliente
            },
            "total_facturas": len(facturas),
            "data": facturas
        }), 200

    except Exception as e:
        print(
            "Error al obtener las facturas del cliente:",
            str(e)
        )

        return jsonify({
            "error": "Error en la consulta de facturas"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if conexion and conexion.is_connected():
            conexion.close()


# ============================================================
# FACTURAS POR GRUPO
# ============================================================
@clientes_bp.route('/facturas-grupo/<int:id_grupo>', methods=['GET'])
@token_required
def obtener_facturas_grupo(id_grupo):
    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)

        query_facturas = """
            SELECT 
                m.*
            FROM monitor m
            JOIN clientes c
                ON m.contacto_referencia = c.clave
            WHERE c.id_grupo = %s
              AND c.activo = 1
              AND m.fecha_factura >= c.f_inicio
              AND m.numero_factura IS NOT NULL
              AND m.numero_factura != '/'
            ORDER BY
                m.fecha_factura DESC
        """

        cursor.execute(
            query_facturas,
            (id_grupo,)
        )

        facturas = cursor.fetchall()

        for factura in facturas:
            if (
                factura.get('fecha_factura')
                and isinstance(
                    factura['fecha_factura'],
                    (datetime, date)
                )
            ):
                factura['fecha_factura'] = factura[
                    'fecha_factura'
                ].strftime('%Y-%m-%d %H:%M:%S')

        return jsonify({
            "success": True,
            "data": facturas
        }), 200

    except Exception as e:
        print(
            f"Error al obtener facturas del grupo: {str(e)}"
        )

        return jsonify({
            "error": "Error en la consulta de facturas del grupo"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if conexion and conexion.is_connected():
            conexion.close()