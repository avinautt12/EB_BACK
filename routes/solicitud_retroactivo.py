from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
import logging
import os

from flask import Blueprint, jsonify, request
from db_conexion import obtener_conexion
from services.s3_service import generar_url_firmada_s3, subir_archivo_s3
from services import solicitud_retroactivo_service as data
from utils.jwt_utils import verificar_token

solicitud_retroactivo_bp = Blueprint('solicitud-retroactivo', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'uploads', 'solicitudes-retroactivos')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'xml'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Definimos los campos de archivos que esperamos recibir
ARCHIVOS_REQUERIDOS = {
    "ticket_compra": "Ticket de compra",
    "voucher": "Voucher de pago",
    "factura_pdf": "Factura PDF",
    "factura_xml": "Factura XML"
}


def _usuario_desde_token(request):
    """Decodifica el JWT del header Authorization. None si falta o es inválido."""
    auth_header = request.headers.get('Authorization', '')
    raw_token = auth_header.split(' ')[1] if ' ' in auth_header else None
    if not raw_token:
        return None
    return verificar_token(raw_token)


def _requiere_admin(request):
    """Ver routes/retroactivos.py:_requiere_admin_retroactivos, mismo patrón."""
    payload = _usuario_desde_token(request)
    if not payload:
        return False
    try:
        return int(payload.get('rol')) == 1
    except (TypeError, ValueError):
        return False


def _parsear_validacion_docs(raw):
    """validacion_docs_json puede venir como dict (ya parseado), str (JSON
    crudo) o None (nadie ha revisado nada todavía)."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {}


# GUÍA: historial como columna JSON (mismo patrón que validacion_docs_json)
# en vez de una tabla de auditoría nueva -- no hay volumen que justifique una
# tabla aparte, y evita otra migración + endpoint. Cada mutación relevante
# (creación, validar/rechazar documento, corrección de precio, reenvío del
# cliente) le agrega una entrada. Se expone en listar/mis-solicitudes.
def _parsear_historial(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return []


def _entrada_historial(tipo, descripcion):
    return {"fecha": datetime.now().isoformat(), "tipo": tipo, "descripcion": descripcion}


# GUÍA: validación por archivo, no por solicitud completa -- si el admin
# rechaza 1 de los 4 documentos, la solicitud se ve como 'rechazado' en su
# conjunto (decisión de producto: más simple de entender para el cliente que
# un estado "parcial"), pero el cliente solo tiene que resubir ESE archivo
# (ver PUT /venta/<id>), no los 4. Solo es 'validado' cuando los 4 quedaron
# marcados 'valido'. Sin nada rechazado y sin completar, sigue 'pendiente'.
def _calcular_estatus(validacion_docs):
    if 'rechazado' in validacion_docs.values():
        return 'rechazado'
    if all(validacion_docs.get(k) == 'valido' for k in ARCHIVOS_REQUERIDOS):
        return 'validado'
    return 'pendiente'

@solicitud_retroactivo_bp.route('/api/solicitud-retroactivo/registrar/venta', methods=['POST'])
def registrar_venta():
    # 1. Recuperar los campos del formulario
    campos_obligatorios = [
        'id_usuario', 'id_formulario', 'id_msi', 'nombre_sucursal',
        'correo_electronico', 'nombre_completo', 'fecha_venta',
        'modelo_bicicleta', 'numero_serie', 'precio_publico'
    ]

    datos = {campo: request.form.get(campo) for campo in campos_obligatorios}
    datos['id_marca_bicicleta'] = request.form.get('id_marca_bicicleta')

    # Validar que ningún campo obligatorio esté vacío
    faltantes = [campo for campo, valor in datos.items() if campo in campos_obligatorios and not valor]
    if faltantes:
        return jsonify({
            "error": "Campos de texto faltantes",
            "campos": faltantes
        }), 400

    # 2. Validar que los 4 archivos estén presentes
    for key_archivo in ARCHIVOS_REQUERIDOS.keys():
        if key_archivo not in request.files:
            return jsonify({"error": f"No se recibió el archivo: {key_archivo}"}), 400

        file = request.files[key_archivo]

        if not file.filename:
            return jsonify({"error": f"Nombre de archivo vacío para: {key_archivo}"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": f"Tipo de archivo no permitido para: {key_archivo}"}), 400

    # 3. Subida de archivos a AWS S3 PRIMERO. GUÍA: antes, la key que se
    # guardaba en BD se fabricaba a mano (f"retroactivos/{numero_serie}_...")
    # y NUNCA era la key real que subir_archivo_s3 le da al objeto (esa usa
    # UUID + AWS_S3_PREFIX). Cualquier venta registrada así quedaba con
    # archivos huérfanos -- la key en BD no le pertenecía a ningún objeto en
    # S3. Ahora se sube primero y se usa la key que S3 realmente asignó.
    archivos_procesados = {}
    keys_archivos = {}

    try:
        for key_archivo in ARCHIVOS_REQUERIDOS.keys():
            file = request.files[key_archivo]
            resultado = subir_archivo_s3(file)

            keys_archivos[key_archivo] = resultado["key"]
            archivos_procesados[key_archivo] = {
                "key": resultado["key"],
                "original": resultado["original"],
                "url": generar_url_firmada_s3(resultado["key"]),
                "storage": "s3"
            }

    except Exception as e:
        logging.exception("Error al subir archivos a S3: %s", e)
        return jsonify({"error": "Ocurrió un error al subir los archivos."}), 500

    # 4. Operaciones de Base de Datos, ya con las keys reales de S3
    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500

    cursor = conexion.cursor(dictionary=True, buffered=True)

    try:
        raw_marca = datos.get('id_marca_bicicleta')
        id_marca = int(raw_marca) if raw_marca and str(raw_marca).isdigit() else None

        # Consulta del porcentaje desde la función SQL
        id_msi_seleccionado = int(datos['id_msi'])
        resultado = data.obtener_porcentaje_msi(cursor, id_msi_seleccionado)

        porcentaje_val = resultado['porcentaje'] if resultado and resultado['porcentaje'] is not None else 0
        porcentaje = Decimal(str(porcentaje_val))

        # Cálculos numéricos
        precio_publico = Decimal(str(datos['precio_publico']).replace(',', ''))
        monto_pagar = (precio_publico * porcentaje) / Decimal(100)
        monto_aplicar = monto_pagar

        # Parámetros para el Stored Procedure
        parametros = (
            int(datos['id_usuario']),
            int(datos['id_formulario']),
            id_marca,
            id_msi_seleccionado,
            datos['nombre_sucursal'],
            datos['correo_electronico'],
            datos['nombre_completo'],
            datos['fecha_venta'],
            datos['modelo_bicicleta'],
            datos['numero_serie'],
            precio_publico,
            porcentaje,
            monto_pagar,
            monto_aplicar,
            keys_archivos['ticket_compra'],
            keys_archivos['voucher'],
            keys_archivos['factura_pdf'],
            keys_archivos['factura_xml']
        )

        data.crear_venta(cursor, parametros)
        conexion.commit()

        # numero_serie es UNIQUE, así se identifica la fila recién creada sin
        # depender de que el SP regrese el id (no lo hace).
        nueva = data.obtener_id_por_numero_serie(cursor, datos['numero_serie'])
        if nueva:
            data.guardar_historial_inicial(
                cursor, nueva['id'],
                json.dumps([_entrada_historial('creacion', 'Solicitud registrada')])
            )
            conexion.commit()

        return jsonify({
            "respuesta": True,
            "mensaje": "Venta y archivos registrados exitosamente",
            "datos_venta": datos,
            "archivos": archivos_procesados
        }), 200

    except Exception as e:
        conexion.rollback()
        logging.exception("Error en BD al registrar la venta: %s", e)
        return jsonify({"error": "Los archivos se subieron pero ocurrió un error al registrar la venta en la base de datos.", "detalle": str(e)}), 500
    finally:
        cursor.close()
        conexion.close()

@solicitud_retroactivo_bp.route('/api/solicitud-retroactivo/msi', methods=['GET'])
def buscar_msi():
    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500
           
    cursor = conexion.cursor(dictionary=True, buffered=True) 
    
    try:
        datos = data.buscar_msi(cursor)
        return jsonify(datos), 200

    except Exception as e:
        return jsonify({"error": "Error al consultar los meses sin intereses.", "detalle": str(e)}), 500
        
    finally:
        cursor.close()
        conexion.close()

@solicitud_retroactivo_bp.route('/api/solicitud-retroactivo/marca', methods=['GET'])
def buscar_marca():
    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500
           
    cursor = conexion.cursor(dictionary=True, buffered=True) 
    
    try:
        datos = data.buscar_marca(cursor)
        return jsonify(datos), 200

    except Exception as e:
        return jsonify({"error": "Error al consultar las marcas.", "detalle": str(e)}), 500
        
    finally:
        cursor.close()
        conexion.close()

@solicitud_retroactivo_bp.route('/api/solicitud-retroactivo/formulario', methods=['GET'])
def buscar_formulario():
    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500
           
    cursor = conexion.cursor(dictionary=True, buffered=True) 
    
    try:
        datos = data.buscar_formulario(cursor)
        return jsonify(datos), 200

    except Exception as e:
        return jsonify({"error": "Error al consultar las marcas.", "detalle": str(e)}), 500

    finally:
        cursor.close()
        conexion.close()


@solicitud_retroactivo_bp.route('/api/solicitud-retroactivo/listar', methods=['GET'])
def listar_solicitudes():
    if not _requiere_admin(request):
        return jsonify({"error": "No autorizado"}), 403

    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500

    cursor = conexion.cursor(dictionary=True, buffered=True)
    try:
        filas = data.listar_ventas(cursor)

        # Firma las URLs al vuelo (las guardadas al momento del registro expiran)
        # y arma el detalle de validación por archivo + el estatus general.
        for fila in filas:
            validacion_docs = _parsear_validacion_docs(fila.pop('validacion_docs_json'))
            fila['estatus'] = _calcular_estatus(validacion_docs)
            fila['historial'] = _parsear_historial(fila.pop('historial_json'))
            fila['archivos'] = {}
            for campo, nombre in (
                ('ticket_compra_key', 'ticket_compra'), ('voucher_key', 'voucher'),
                ('factura_pdf_key', 'factura_pdf'), ('factura_xml_key', 'factura_xml'),
            ):
                key = fila.pop(campo)
                fila['archivos'][nombre] = {
                    "key": key,
                    "url": generar_url_firmada_s3(key) if key else None,
                    "estatus": validacion_docs.get(nombre, 'pendiente')
                }

        return jsonify(filas), 200

    except Exception as e:
        logging.exception("Error al listar solicitudes de retroactivo: %s", e)
        return jsonify({"error": "Error al listar las solicitudes.", "detalle": str(e)}), 500
    finally:
        cursor.close()
        conexion.close()


@solicitud_retroactivo_bp.route('/api/solicitud-retroactivo/dashboard', methods=['GET'])
def dashboard_solicitudes():
    if not _requiere_admin(request):
        return jsonify({"error": "No autorizado"}), 403

    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500

    cursor = conexion.cursor(dictionary=True, buffered=True)
    try:
        totales_generales = data.obtener_totales_generales(cursor)

        # GUÍA: pendientes/validados/rechazados ya no viven en la columna
        # 'validado' (esa quedó sin usar desde que la validación pasó a ser
        # por archivo) -- se derivan de validacion_docs_json en Python, igual
        # que en listar_solicitudes/mis_solicitudes.
        conteo = {"pendiente": 0, "validado": 0, "rechazado": 0}
        for fila in data.obtener_validaciones_docs(cursor):
            estatus = _calcular_estatus(_parsear_validacion_docs(fila['validacion_docs_json']))
            conteo[estatus] += 1
        totales_generales['pendientes'] = conteo['pendiente']
        totales_generales['validados'] = conteo['validado']
        totales_generales['rechazados'] = conteo['rechazado']

        por_campana = data.obtener_dashboard_por_campana(cursor)
        por_cliente = data.obtener_dashboard_por_cliente(cursor)
        por_anio_modelo = data.obtener_dashboard_por_anio_modelo(cursor)

        return jsonify({
            "totales_generales": totales_generales,
            "por_campana": por_campana,
            "por_cliente": por_cliente,
            "por_anio_modelo": por_anio_modelo
        }), 200

    except Exception as e:
        logging.exception("Error al generar dashboard de solicitudes de retroactivo: %s", e)
        return jsonify({"error": "Error al generar el dashboard.", "detalle": str(e)}), 500
    finally:
        cursor.close()
        conexion.close()


@solicitud_retroactivo_bp.route('/api/solicitud-retroactivo/validar-documento/<int:id_venta>', methods=['POST'])
def validar_documento(id_venta):
    if not _requiere_admin(request):
        return jsonify({"error": "No autorizado"}), 403

    body = request.get_json(force=True, silent=True) or {}
    documento = body.get('documento')
    estatus_doc = body.get('estatus')

    if documento not in ARCHIVOS_REQUERIDOS:
        return jsonify({"error": "Documento inválido."}), 400
    if estatus_doc not in ('valido', 'rechazado'):
        return jsonify({"error": "Estatus inválido, debe ser 'valido' o 'rechazado'."}), 400

    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500

    cursor = conexion.cursor(dictionary=True, buffered=True)
    try:
        fila = data.obtener_venta_para_validacion(cursor, id_venta)
        if not fila:
            return jsonify({"error": "Solicitud no encontrada."}), 404

        validacion_docs = _parsear_validacion_docs(fila['validacion_docs_json'])
        validacion_docs[documento] = estatus_doc

        etiqueta_doc = ARCHIVOS_REQUERIDOS[documento]
        etiqueta_estatus = 'validado' if estatus_doc == 'valido' else 'rechazado'
        historial = _parsear_historial(fila['historial_json'])
        historial.append(_entrada_historial('validacion', f"{etiqueta_doc}: {etiqueta_estatus}"))

        data.actualizar_validacion_documento(cursor, id_venta, json.dumps(validacion_docs), json.dumps(historial))
        conexion.commit()

        return jsonify({
            "ok": True,
            "id": id_venta,
            "validacion_docs": validacion_docs,
            "estatus": _calcular_estatus(validacion_docs),
            "historial": historial
        }), 200

    except Exception as e:
        conexion.rollback()
        logging.exception("Error al validar documento de solicitud %s: %s", id_venta, e)
        return jsonify({"error": "Error al actualizar la solicitud.", "detalle": str(e)}), 500
    finally:
        cursor.close()
        conexion.close()


# GUÍA: el precio lo escribe el cliente a mano en el formulario y a veces se
# equivoca (typo, número mal leído del ticket). En vez de rechazar TODA la
# solicitud por un dato que el admin puede verificar contra la factura/ticket
# adjuntos, el admin lo corrige directo aquí -- no pasa por el flujo de
# rechazo/reenvío de archivos. Recalcula monto_pagar/monto_aplicar con el
# mismo porcentaje ya guardado (el % depende del plan MSI, no del precio).
@solicitud_retroactivo_bp.route('/api/solicitud-retroactivo/precio/<int:id_venta>', methods=['POST'])
def corregir_precio(id_venta):
    if not _requiere_admin(request):
        return jsonify({"error": "No autorizado"}), 403

    body = request.get_json(force=True, silent=True) or {}
    nuevo_precio_raw = body.get('precio_publico')
    if nuevo_precio_raw is None:
        return jsonify({"error": "Falta precio_publico."}), 400

    try:
        nuevo_precio = Decimal(str(nuevo_precio_raw).replace(',', ''))
        if nuevo_precio < 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        return jsonify({"error": "precio_publico inválido."}), 400

    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500

    cursor = conexion.cursor(dictionary=True, buffered=True)
    try:
        fila = data.obtener_venta_para_precio(cursor, id_venta)
        if not fila:
            return jsonify({"error": "Solicitud no encontrada."}), 404

        porcentaje = fila['porcentaje'] or Decimal('0')
        monto = (nuevo_precio * porcentaje) / Decimal(100)

        historial = _parsear_historial(fila['historial_json'])
        historial.append(_entrada_historial(
            'precio', f"Precio corregido de ${fila['precio_publico']} a ${nuevo_precio}"
        ))

        data.actualizar_precio(cursor, id_venta, nuevo_precio, monto, monto, json.dumps(historial))
        conexion.commit()

        return jsonify({
            "ok": True,
            "id": id_venta,
            "precio_publico": str(nuevo_precio),
            "monto_pagar": str(monto),
            "monto_aplicar": str(monto)
        }), 200

    except Exception as e:
        conexion.rollback()
        logging.exception("Error al corregir precio de solicitud %s: %s", id_venta, e)
        return jsonify({"error": "Error al actualizar el precio.", "detalle": str(e)}), 500
    finally:
        cursor.close()
        conexion.close()


@solicitud_retroactivo_bp.route('/api/solicitud-retroactivo/mis-solicitudes', methods=['GET'])
def mis_solicitudes():
    payload = _usuario_desde_token(request)
    if not payload:
        return jsonify({"error": "No autorizado"}), 401

    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500

    cursor = conexion.cursor(dictionary=True, buffered=True)
    try:
        filas = data.listar_mis_ventas(cursor, payload.get('id'))

        # GUÍA: el cliente ve exactamente lo mismo que el admin en el Gestor
        # (todos los campos, estatus por archivo con su URL para previsualizar
        # lo que subió, e historial de cambios) -- solo que de sus propias
        # solicitudes. Necesita saber EXACTAMENTE qué archivo(s) fueron
        # rechazados para poder resubir solo esos (ver PUT /venta/<id>).
        for fila in filas:
            validacion_docs = _parsear_validacion_docs(fila.pop('validacion_docs_json'))
            fila['estatus'] = _calcular_estatus(validacion_docs)
            fila['validacion_docs'] = validacion_docs
            fila['historial'] = _parsear_historial(fila.pop('historial_json'))

            fila['archivos'] = {}
            for campo, nombre in (
                ('ticket_compra_key', 'ticket_compra'), ('voucher_key', 'voucher'),
                ('factura_pdf_key', 'factura_pdf'), ('factura_xml_key', 'factura_xml'),
            ):
                key = fila.pop(campo)
                fila['archivos'][nombre] = {
                    "key": key,
                    "url": generar_url_firmada_s3(key) if key else None,
                    "estatus": validacion_docs.get(nombre, 'pendiente')
                }

        return jsonify(filas), 200
    except Exception as e:
        logging.exception("Error al listar mis-solicitudes: %s", e)
        return jsonify({"error": "Error al consultar tus solicitudes.", "detalle": str(e)}), 500
    finally:
        cursor.close()
        conexion.close()


@solicitud_retroactivo_bp.route('/api/solicitud-retroactivo/venta/<int:id_venta>', methods=['PUT'])
def editar_venta(id_venta):
    payload = _usuario_desde_token(request)
    if not payload:
        return jsonify({"error": "No autorizado"}), 401

    campos_obligatorios = [
        'id_formulario', 'id_msi', 'nombre_sucursal',
        'correo_electronico', 'nombre_completo', 'fecha_venta',
        'modelo_bicicleta', 'numero_serie', 'precio_publico'
    ]
    datos = {campo: request.form.get(campo) for campo in campos_obligatorios}
    datos['id_marca_bicicleta'] = request.form.get('id_marca_bicicleta')

    faltantes = [campo for campo, valor in datos.items() if campo in campos_obligatorios and not valor]
    if faltantes:
        return jsonify({"error": "Campos de texto faltantes", "campos": faltantes}), 400

    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500

    cursor = conexion.cursor(dictionary=True, buffered=True)

    try:
        # GUÍA: solo el dueño de la solicitud puede reeditarla, y solo
        # mientras esté rechazada (algún documento marcado 'rechazado').
        # Solo se piden/reemplazan los archivos rechazados -- los que ya
        # estaban 'valido' se quedan tal cual en S3, no hace falta resubirlos.
        fila = data.obtener_venta_para_edicion(cursor, id_venta)
        if not fila:
            return jsonify({"error": "Solicitud no encontrada."}), 404
        if fila['id_usuario'] != payload.get('id'):
            return jsonify({"error": "No autorizado"}), 403

        validacion_docs = _parsear_validacion_docs(fila['validacion_docs_json'])
        if _calcular_estatus(validacion_docs) != 'rechazado':
            return jsonify({"error": "Solo se pueden editar solicitudes con algún archivo rechazado."}), 400

        docs_a_resubir = [k for k in ARCHIVOS_REQUERIDOS if validacion_docs.get(k) == 'rechazado']
        historial = _parsear_historial(fila['historial_json'])
    except Exception as e:
        logging.exception("Error al validar propiedad de la solicitud %s: %s", id_venta, e)
        return jsonify({"error": "Error al verificar la solicitud.", "detalle": str(e)}), 500
    finally:
        cursor.close()
        conexion.close()

    faltantes_archivos = []
    for key_archivo in docs_a_resubir:
        file = request.files.get(key_archivo)
        if not file or not file.filename:
            faltantes_archivos.append(key_archivo)
        elif not allowed_file(file.filename):
            return jsonify({"error": f"Tipo de archivo no permitido para: {key_archivo}"}), 400
    if faltantes_archivos:
        return jsonify({
            "error": "Faltan los archivos rechazados por corregir",
            "campos": faltantes_archivos
        }), 400

    # Subida a S3 primero (mismo motivo que en registrar_venta: la key en BD
    # debe ser la key real que S3 asigna, no una fabricada). Solo se suben
    # los archivos que estaban rechazados.
    archivos_procesados = {}
    keys_archivos = {}
    try:
        for key_archivo in docs_a_resubir:
            file = request.files[key_archivo]
            resultado = subir_archivo_s3(file)
            keys_archivos[key_archivo] = resultado["key"]
            archivos_procesados[key_archivo] = {
                "key": resultado["key"],
                "original": resultado["original"],
                "url": generar_url_firmada_s3(resultado["key"]),
                "storage": "s3"
            }
    except Exception as e:
        logging.exception("Error al subir archivos a S3 al reeditar la venta %s: %s", id_venta, e)
        return jsonify({"error": "Ocurrió un error al subir los archivos."}), 500

    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500

    cursor = conexion.cursor(dictionary=True, buffered=True)
    try:
        raw_marca = datos.get('id_marca_bicicleta')
        id_marca = int(raw_marca) if raw_marca and str(raw_marca).isdigit() else None

        id_msi_seleccionado = int(datos['id_msi'])
        resultado = data.obtener_porcentaje_msi(cursor, id_msi_seleccionado)
        porcentaje_val = resultado['porcentaje'] if resultado and resultado['porcentaje'] is not None else 0
        porcentaje = Decimal(str(porcentaje_val))

        precio_publico = Decimal(str(datos['precio_publico']).replace(',', ''))
        monto_pagar = (precio_publico * porcentaje) / Decimal(100)
        monto_aplicar = monto_pagar

        # Los archivos resubidos vuelven a 'pendiente' (se quitan del dict);
        # los que ya estaban 'valido' se quedan intactos.
        for key_archivo in docs_a_resubir:
            validacion_docs.pop(key_archivo, None)

        etiquetas_resubidas = ', '.join(ARCHIVOS_REQUERIDOS[k] for k in docs_a_resubir)
        historial.append(_entrada_historial('reenvio', f"Cliente reenvió: {etiquetas_resubidas}"))

        columnas_archivo = ', '.join(f"{k}_key = %s" for k in docs_a_resubir)
        valores_archivo = [keys_archivos[k] for k in docs_a_resubir]

        valores_fijos = (
            int(datos['id_formulario']), id_marca, id_msi_seleccionado,
            datos['nombre_sucursal'], datos['correo_electronico'], datos['nombre_completo'],
            datos['fecha_venta'], datos['modelo_bicicleta'], datos['numero_serie'],
            precio_publico, porcentaje, monto_pagar, monto_aplicar,
            json.dumps(validacion_docs), json.dumps(historial),
        )
        data.actualizar_venta(cursor, id_venta, valores_fijos, columnas_archivo, valores_archivo)
        conexion.commit()

        return jsonify({
            "respuesta": True,
            "mensaje": "Solicitud actualizada y enviada de nuevo a revisión.",
            "archivos": archivos_procesados,
            "historial": historial
        }), 200

    except Exception as e:
        conexion.rollback()
        logging.exception("Error en BD al editar la venta %s: %s", id_venta, e)
        return jsonify({"error": "Los archivos se subieron pero ocurrió un error al actualizar la venta.", "detalle": str(e)}), 500
    finally:
        cursor.close()
        conexion.close()