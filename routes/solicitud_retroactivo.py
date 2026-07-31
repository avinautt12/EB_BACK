from decimal import Decimal
import logging
import os

from flask import Blueprint, jsonify, request
from db_conexion import obtener_conexion
from services.s3_service import generar_url_firmada_s3, subir_archivo_s3

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

ARCHIVOS_REQUERIDOS = {
    "ticket_compra": "Ticket de compra",
    "voucher": "Voucher de pago",
    "factura_pdf": "Factura PDF",
    "factura_xml": "Factura XML"
}

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

    # 3. Operaciones de Base de Datos PRIMERO
    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500

    cursor = conexion.cursor(dictionary=True, buffered=True)

    try:
        raw_marca = datos.get('id_marca_bicicleta')
        id_marca = int(raw_marca) if raw_marca and str(raw_marca).isdigit() else 0

        # Consulta del porcentaje desde la función SQL
        id_msi_seleccionado = int(datos['id_msi'])
        query = "SELECT fn_ObtenerPorcentajeMsi(%s) AS porcentaje;"
        cursor.execute(query, (id_msi_seleccionado,))
        resultado = cursor.fetchone()
        
        porcentaje_val = resultado['porcentaje'] if resultado and resultado['porcentaje'] is not None else 0
        porcentaje = Decimal(str(porcentaje_val))
        
        # Cálculos numéricos
        precio_publico = Decimal(str(datos['precio_publico']).replace(',', ''))
        monto_pagar = (precio_publico * porcentaje) / Decimal(100)
        monto_aplicar = monto_pagar

        # Generar keys proyectadas para S3
        keys_archivos = {
            key: f"retroactivos/{datos['numero_serie']}_{key}_{request.files[key].filename}"
            for key in ARCHIVOS_REQUERIDOS.keys()
        }

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

        cursor.callproc('sp_solicitud_retroactivo_crear_venta', parametros)
        conexion.commit()

        while cursor.nextset():
            pass

    except Exception as e:
        conexion.rollback()
        logging.exception("Error en BD al registrar la venta: %s", e)
        return jsonify({"error": "Error al registrar la venta en la base de datos.", "detalle": str(e)}), 500
    finally:
        cursor.close()
        conexion.close()

    # 4. Subida de archivos a AWS S3
    archivos_procesados = {}
    keys_subidas = []

    try:
        for key_archivo in ARCHIVOS_REQUERIDOS.keys():
            file = request.files[key_archivo]

            resultado = subir_archivo_s3(file) 
            keys_subidas.append(resultado["key"])
            
            url = generar_url_firmada_s3(resultado["key"])

            archivos_procesados[key_archivo] = {
                "key": resultado["key"],
                "original": resultado["original"],
                "url": url,
                "storage": "s3"
            }

        return jsonify({
            "respuesta": True,
            "mensaje": "Venta y archivos registrados exitosamente",
            "datos_venta": datos,
            "archivos": archivos_procesados
        }), 200

    except Exception as e:
        logging.exception("Error al subir archivos a S3 tras guardar en BD: %s", e)
        
        # # Rollback de archivos subidos si falla la red
        # for key in keys_subidas:
        #     try:
        #         eliminar_archivo_s3(key)
        #     except Exception as del_err:
        #         logging.error("No se pudo eliminar el archivo huérfano %s: %s", key, del_err)

        return jsonify({"error": "Se guardó el registro pero ocurrió un error al subir los archivos."}), 500

@solicitud_retroactivo_bp.route('/api/solicitud-retroactivo/msi', methods=['GET'])
def buscar_msi():
    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500
           
    cursor = conexion.cursor(dictionary=True, buffered=True) 
    
    try:
        cursor.callproc('sp_solicitud_retroactivo_buscar_msi')
        datos = []
        for resultado in cursor.stored_results():
            datos = resultado.fetchall()
            
        while cursor.nextset():
            pass
            
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
        cursor.callproc('sp_solicitud_retroactivo_buscar_marca')
        datos = []
        for resultado in cursor.stored_results():
            datos = resultado.fetchall()
            
        while cursor.nextset():
            pass
            
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
        cursor.callproc('sp_solicitud_retroactivo_buscar_formulario')
        datos = []
        for resultado in cursor.stored_results():
            datos = resultado.fetchall()
            
        while cursor.nextset():
            pass
            
        return jsonify(datos), 200
        
    except Exception as e:
        return jsonify({"error": "Error al consultar las marcas.", "detalle": str(e)}), 500
        
    finally:
        cursor.close()
        conexion.close()