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

@solicitud_retroactivo_bp.route('/api/solicitud-retroactivo/registrar/venta', methods=['POST'])
def registrar_venta():
    # 1. Recuperar y validar los campos de texto del formulario
    campos_texto = [
        'razon_social', 'marca_bicicleta', 'venta_msi', 'nombre_sucursal',
        'correo_electronico', 'nombre_completo', 'fecha_venta',
        'modelo_bicicleta', 'numero_serie'
    ]

    datos = {campo: request.form.get(campo) for campo in campos_texto}

    # Validar que ningún campo de texto esté vacío
    faltantes = [campo for campo, valor in datos.items() if not valor]
    if faltantes:
        return jsonify({
            "error": "Campos de texto faltantes",
            "campos": faltantes
        }), 400

    # 2. Validar que los 4 archivos estén presentes en la solicitud
    for key_archivo in ARCHIVOS_REQUERIDOS.keys():
        if key_archivo not in request.files:
            return jsonify({"error": f"No se recibió el archivo: {key_archivo}"}), 400

        file = request.files[key_archivo]

        if not file.filename:
            return jsonify({"error": f"Nombre de archivo vacío para: {key_archivo}"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": f"Tipo de archivo no permitido para: {key_archivo}"}), 400

    # 3. Subir los archivos a S3 y generar sus URLs firmadas
    archivos_procesados = {}

    try:
        for key_archivo in ARCHIVOS_REQUERIDOS.keys():
            file = request.files[key_archivo]

            # Reutilizamos tu función de subida existente a S3
            resultado = subir_archivo_s3(file)
            
            # Reutilizamos tu función para generar URL firmada
            url = generar_url_firmada_s3(resultado["key"])

            archivos_procesados[key_archivo] = {
                "key": resultado["key"],
                "original": resultado["original"],
                "url": url,
                "storage": "s3"
            }

        # 4. Guardado en la api
        if archivos_procesados:
            conexion = obtener_conexion()
            if not conexion:
                return jsonify({"error": "No se pudo conectar a la base de datos."}), 500
                    
            cursor = conexion.cursor(dictionary=True, buffered=True) 
            
            try:
                # Recibimos el origen_cliente ('SCOTT' o 'SPRING') enviado desde el formulario
                formulario_cliente = request.form.get('formulario_cliente', 'SCOTT')

                # Empaquetamos los datos en el orden exacto de los parámetros del procedimiento almacenado
                parametros = (
                    int(datos['razon_social']),
                    formulario_cliente,
                    int(datos['marca_bicicleta']),
                    int(datos['venta_msi']),
                    datos['nombre_sucursal'],
                    datos['correo_electronico'],
                    datos['nombre_completo'],
                    datos['fecha_venta'],
                    datos['modelo_bicicleta'],
                    datos['numero_serie'],
                    archivos_procesados['ticket_compra']['key'],
                    archivos_procesados['voucher']['key'],
                    archivos_procesados['factura_pdf']['key'],
                    archivos_procesados['factura_xml']['key']
                )

                # Ejecutamos tu procedimiento con sus correspondientes parámetros
                cursor.callproc('sp_solicitud_retroactivo_crear_venta', parametros)
                conexion.commit()
                    
                while cursor.nextset():
                    pass
                    
            except Exception as e:
                return jsonify({"error": "Error al registrar la venta.", "detalle": str(e)}), 500
                
            finally:
                cursor.close()
                conexion.close()

        # 5. Respuesta exitosa con los datos del registro y las URLs de los archivos
        return jsonify({
            "respuesta": True,
            "mensaje": "Venta registrada exitosamente",
            "datos_venta": datos,
            "archivos": archivos_procesados
        }), 200

    except Exception as e:
        logging.exception("Error al registrar venta y subir archivos a S3: %s", e)
        return jsonify({"error": "Error interno al procesar la venta o subir archivos"}), 500

@solicitud_retroactivo_bp.route('/api/solicitud-retroactivo/cliente/<int:cliente_id>', methods=['GET'])
def buscar_clientes(cliente_id):
    query = (cliente_id == 1 and "sp_solicitud_retroactivo_buscar_cliente_scott" or "sp_solicitud_retroactivo_buscar_cliente_spring")

    conexion = obtener_conexion()
    if not conexion:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 500
           
    cursor = conexion.cursor(dictionary=True, buffered=True) 
    
    try:
        cursor.callproc(query)
        datos = []
        for resultado in cursor.stored_results():
            datos = resultado.fetchall()
            
        while cursor.nextset():
            pass
            
        return jsonify(datos), 200
        
    except Exception as e:
        return jsonify({"error": "Error al consultar los clientes.", "detalle": str(e)}), 500
        
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