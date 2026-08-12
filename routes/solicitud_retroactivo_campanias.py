"""
Rutas API para la administración de campañas de retroactivos.

GUÍA DEL PROYECTO:
- Este archivo contiene únicamente la capa HTTP y la lógica de negocio.
- Las consultas SQL deben vivir en:
    services/solicitud_retroactivos_campanias_service.py
- Las rutas NO deben contener SQL directamente.
- La conexión y el cursor se crean aquí.
- El commit/rollback también se controla aquí.
- El service solamente recibe el cursor y ejecuta consultas.

FUNCIONALIDAD DE CAMPAÑAS:
Una campaña contiene:
    id
    nombre
    fecha_inicio
    fecha_fin
    msi_id
    productos -> arreglo de IDs de productos
    fecha_registro
    activa -> 1 o 0

GUÍA:
- msi_id tiene relación con solicitud_retroactivo_msi.
- productos es una relación de varios productos con una campaña.
- Para no mezclar la lógica de campañas con la tabla MSI, la consulta
  de MSI se mantiene como un endpoint GET independiente.
- fecha_registro se genera/actualiza automáticamente en BD.
- activa permite desactivar una campaña sin eliminarla físicamente.
- DELETE elimina la campaña y sus relaciones de productos.
"""

import json
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request

from db_conexion import obtener_conexion
from services import solicitud_retroactivo_campanias_service as data


# ============================================================
# BLUEPRINT
# ============================================================

solicitud_retroactivo_campanias_bp = Blueprint("solicitud-retroactivo-campanias", __name__)


# ============================================================
# HELPERS
# ============================================================

def _obtener_json():
    """
    Obtiene el body JSON enviado por el frontend.
    """
    return request.get_json(force=True, silent=True) or {}


def _validar_fecha(fecha, nombre_campo):
    """
    Valida que una fecha tenga formato YYYY-MM-DD.
    """
    if not fecha:
        return False, f"El campo {nombre_campo} es obligatorio."

    try:
        datetime.strptime(str(fecha), '%Y-%m-%d')
        return True, None
    except ValueError:
        return False, f"El campo {nombre_campo} debe tener formato YYYY-MM-DD."


def _normalizar_productos(productos):
    """
    Convierte y valida el arreglo de productos.
    """
    if productos is None:
        return []

    if isinstance(productos, str):
        try:
            productos = json.loads(productos)
        except (TypeError, ValueError):
            return None

    if not isinstance(productos, list):
        return None

    resultado = []
    for producto_id in productos:
        try:
            producto_id = int(producto_id)
            if producto_id <= 0:
                return None
            resultado.append(producto_id)
        except (TypeError, ValueError):
            return None

    # Eliminamos duplicados conservando el orden recibido.
    return list(dict.fromkeys(resultado))


def _normalizar_activa(activa, valor_default=1):
    """
    Normaliza el campo activa.
    """
    if activa is None:
        return valor_default

    if isinstance(activa, bool):
        return 1 if activa else 0

    if isinstance(activa, int):
        return activa if activa in (0, 1) else None

    if isinstance(activa, str):
        valor = activa.strip().lower()
        if valor in ('1', 'true'): return 1
        if valor in ('0', 'false'): return 0

    return None


# ============================================================
# GET MSI
# ============================================================

@solicitud_retroactivo_campanias_bp.route('/api/solicitud-retroactivo-campanias/msi', methods=['GET'])
def listar_msi():
    """
    GET - Obtiene la lista de MSI.
    """
    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500

    cursor = conexion.cursor(dictionary=True, buffered=True)

    try:
        datos = data.listar_msi(cursor)
        return jsonify(datos), 200

    except Exception as e:
        logging.exception("Error al consultar MSI para campañas: %s", e)
        return jsonify({
            "error": "Error al consultar los meses sin intereses.",
            "detalle": str(e)
        }), 500

    finally:
        cursor.close()
        conexion.close()


# ============================================================
# GET CAMPAÑAS
# ============================================================

@solicitud_retroactivo_campanias_bp.route('/api/solicitud-retroactivo-campanias', methods=['GET'])
def listar_campanias():
    """
    GET - Lista todas las campañas.
    """
    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500

    cursor = conexion.cursor(dictionary=True, buffered=True)

    try:
        filas = data.listar_campanias(cursor)

        for fila in filas:
            productos = fila.get('productos')
            if productos is None or productos == '':
                fila['productos'] = []
            elif isinstance(productos, list):
                fila['productos'] = productos
            elif isinstance(productos, str):
                try:
                    fila['productos'] = json.loads(productos)
                except (TypeError, ValueError):
                    fila['productos'] = []

        return jsonify(filas), 200

    except Exception as e:
        logging.exception("Error al listar campañas de retroactivos: %s", e)
        return jsonify({
            "error": "Error al listar las campañas.",
            "detalle": str(e)
        }), 500

    finally:
        cursor.close()
        conexion.close()


# ============================================================
# GET CAMPAÑA POR ID
# ============================================================

@solicitud_retroactivo_campanias_bp.route('/api/solicitud-retroactivo-campanias/<int:id_campania>', methods=['GET'])
def obtener_campania(id_campania):
    """
    GET - Obtiene una campaña específica.
    """
    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500

    cursor = conexion.cursor(dictionary=True, buffered=True)

    try:
        fila = data.obtener_campania(cursor, id_campania)
        if not fila:
            return jsonify({"error": "Campaña no encontrada."}), 404

        productos = fila.get('productos')
        if not productos:
            fila['productos'] = []
        elif isinstance(productos, str):
            try:
                fila['productos'] = json.loads(productos)
            except (TypeError, ValueError):
                fila['productos'] = []

        return jsonify(fila), 200

    except Exception as e:
        logging.exception("Error al obtener campaña %s: %s", id_campania, e)
        return jsonify({
            "error": "Error al consultar la campaña.",
            "detalle": str(e)
        }), 500

    finally:
        cursor.close()
        conexion.close()


# ============================================================
# POST CREAR CAMPAÑA
# ============================================================

@solicitud_retroactivo_campanias_bp.route('/api/solicitud-retroactivo-campanias', methods=['POST'])
def crear_campania():
    """
    POST - Crea una campaña.
    """
    body = _obtener_json()

    # Validar nombre
    nombre = body.get('nombre')
    if not nombre or not str(nombre).strip():
        return jsonify({"error": "El campo nombre es obligatorio."}), 400
    nombre = str(nombre).strip()

    # Validar fechas
    fecha_inicio = body.get('fecha_inicio')
    fecha_fin = body.get('fecha_fin')

    valido, error = _validar_fecha(fecha_inicio, 'fecha_inicio')
    if not valido: return jsonify({"error": error}), 400

    valido, error = _validar_fecha(fecha_fin, 'fecha_fin')
    if not valido: return jsonify({"error": error}), 400

    if fecha_fin < fecha_inicio:
        return jsonify({"error": "fecha_fin no puede ser menor que fecha_inicio."}), 400

    # Validar MSI
    msi_id = body.get('msi_id')
    try:
        msi_id = int(msi_id)
        if msi_id <= 0: raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "msi_id inválido."}), 400

    # Validar productos
    productos = _normalizar_productos(body.get('productos'))
    if productos is None:
        return jsonify({"error": "productos debe ser un arreglo de IDs válidos."}), 400

    # Validar activa
    activa = _normalizar_activa(body.get('activa'), valor_default=1)
    if activa is None:
        return jsonify({"error": "activa debe ser 1, 0, true o false."}), 400

    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500

    cursor = conexion.cursor(dictionary=True, buffered=True)

    try:
        msi = data.obtener_msi_por_id(cursor, msi_id)
        if not msi:
            return jsonify({"error": "El MSI indicado no existe."}), 400

        if productos:
            productos_validos = data.validar_productos(cursor, productos)
            ids_validos = {int(p['id']) for p in productos_validos}
            productos_invalidos = [p_id for p_id in productos if p_id not in ids_validos]

            if productos_invalidos:
                return jsonify({
                    "error": "Uno o más productos no existen.",
                    "productos_invalidos": productos_invalidos
                }), 400

        id_campania = data.crear_campania(cursor, nombre, fecha_inicio, fecha_fin, msi_id, activa)

        if productos:
            data.agregar_productos_campania(cursor, id_campania, productos)

        conexion.commit()

        campania = data.obtener_campania(cursor, id_campania)
        
        if campania:
            productos_resultado = campania.get('productos')
            if not productos_resultado:
                campania['productos'] = []
            elif isinstance(productos_resultado, str):
                try:
                    campania['productos'] = json.loads(productos_resultado)
                except (TypeError, ValueError):
                    campania['productos'] = []

        return jsonify({
            "respuesta": True,
            "mensaje": "Campaña creada correctamente.",
            "datos": campania
        }), 201

    except Exception as e:
        conexion.rollback()
        logging.exception("Error al crear campaña de retroactivo: %s", e)
        return jsonify({
            "error": "Error al crear la campaña.",
            "detalle": str(e)
        }), 500

    finally:
        cursor.close()
        conexion.close()


# ============================================================
# PUT EDITAR CAMPAÑA
# ============================================================

@solicitud_retroactivo_campanias_bp.route('/api/solicitud-retroactivo-campanias/<int:id_campania>', methods=['PUT'])
def editar_campania(id_campania):
    """
    PUT - Edita una campaña.
    """
    body = _obtener_json()
    conexion = obtener_conexion()

    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500

    cursor = conexion.cursor(dictionary=True, buffered=True)

    try:
        existente = data.obtener_campania(cursor, id_campania)
        if not existente:
            return jsonify({"error": "Campaña no encontrada."}), 404

        # Validar nombre
        nombre = body.get('nombre')
        if not nombre or not str(nombre).strip():
            return jsonify({"error": "El campo nombre es obligatorio."}), 400
        nombre = str(nombre).strip()

        # Validar fechas
        fecha_inicio = body.get('fecha_inicio')
        fecha_fin = body.get('fecha_fin')

        valido, error = _validar_fecha(fecha_inicio, 'fecha_inicio')
        if not valido: return jsonify({"error": error}), 400

        valido, error = _validar_fecha(fecha_fin, 'fecha_fin')
        if not valido: return jsonify({"error": error}), 400

        if fecha_fin < fecha_inicio:
            return jsonify({"error": "fecha_fin no puede ser menor que fecha_inicio."}), 400

        # Validar MSI
        msi_id = body.get('msi_id')
        try:
            msi_id = int(msi_id)
            if msi_id <= 0: raise ValueError
        except (TypeError, ValueError):
            return jsonify({"error": "msi_id inválido."}), 400

        msi = data.obtener_msi_por_id(cursor, msi_id)
        if not msi:
            return jsonify({"error": "El MSI indicado no existe."}), 400

        # Validar productos
        productos = _normalizar_productos(body.get('productos'))
        if productos is None:
            return jsonify({"error": "productos debe ser un arreglo de IDs válidos."}), 400

        if productos:
            productos_validos = data.validar_productos(cursor, productos)
            ids_validos = {int(p['id']) for p in productos_validos}
            productos_invalidos = [p_id for p_id in productos if p_id not in ids_validos]

            if productos_invalidos:
                return jsonify({
                    "error": "Uno o más productos no existen.",
                    "productos_invalidos": productos_invalidos
                }), 400

        # Validar activa
        activa = _normalizar_activa(body.get('activa'), valor_default=existente.get('activa', 1))
        if activa is None:
            return jsonify({"error": "activa debe ser 1, 0, true o false."}), 400

        # Actualizar campaña
        data.actualizar_campania(cursor, id_campania, nombre, fecha_inicio, fecha_fin, msi_id, activa)
        data.eliminar_productos_campania(cursor, id_campania)

        if productos:
            data.agregar_productos_campania(cursor, id_campania, productos)

        conexion.commit()

        campania = data.obtener_campania(cursor, id_campania)
        if campania:
            productos_resultado = campania.get('productos')
            if not productos_resultado:
                campania['productos'] = []
            elif isinstance(productos_resultado, str):
                try:
                    campania['productos'] = json.loads(productos_resultado)
                except (TypeError, ValueError):
                    campania['productos'] = []

        return jsonify({
            "respuesta": True,
            "mensaje": "Campaña actualizada correctamente.",
            "datos": campania
        }), 200

    except Exception as e:
        conexion.rollback()
        logging.exception("Error al editar campaña %s: %s", id_campania, e)
        return jsonify({
            "error": "Error al actualizar la campaña.",
            "detalle": str(e)
        }), 500

    finally:
        cursor.close()
        conexion.close()


# ============================================================
# DELETE CAMPAÑA
# ============================================================

@solicitud_retroactivo_campanias_bp.route('/api/solicitud-retroactivo-campanias/<int:id_campania>', methods=['DELETE'])
def eliminar_campania(id_campania):
    """
    DELETE - Elimina una campaña.
    """
    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500

    cursor = conexion.cursor(dictionary=True, buffered=True)

    try:
        existente = data.obtener_campania(cursor, id_campania)
        if not existente:
            return jsonify({"error": "Campaña no encontrada."}), 404

        data.eliminar_productos_campania(cursor, id_campania)
        data.eliminar_campania(cursor, id_campania)
        conexion.commit()

        return jsonify({
            "respuesta": True,
            "mensaje": "Campaña eliminada correctamente.",
            "id": id_campania
        }), 200

    except Exception as e:
        conexion.rollback()
        logging.exception("Error al eliminar campaña %s: %s", id_campania, e)
        return jsonify({
            "error": "Error al eliminar la campaña.",
            "detalle": str(e)
        }), 500

    finally:
        cursor.close()
        conexion.close()