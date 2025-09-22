from flask import Blueprint, request, jsonify
import pandas as pd
from db_conexion import obtener_conexion
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from models.monitor_odoo_model import obtener_todos_los_registros
import re
from zoneinfo import ZoneInfo

monitor_odoo_bp = Blueprint('monitor_odoo', __name__, url_prefix='')

@monitor_odoo_bp.route('/monitor_odoo', methods=['GET'])
def obtener_monitor():
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        consulta = """
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
        """
        cursor.execute(consulta)
        resultados = cursor.fetchall()
        return jsonify(resultados)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@monitor_odoo_bp.route('/ultima_actualizacion', methods=['GET'])
def obtener_ultima_actualizacion():
    """
    Esta función obtiene la fecha más reciente de la tabla 'historial_actualizaciones'
    para saber cuándo se realizó la última importación de datos.
    """
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)

        consulta = """
        SELECT MAX(fecha_actualizacion) as ultima_fecha
        FROM historial_actualizaciones
        """
        
        cursor.execute(consulta)
        resultado = cursor.fetchone()
        
        if resultado and resultado['ultima_fecha']:
            return jsonify({
                'success': True,
                'ultima_fecha_actualizacion': resultado['ultima_fecha'].isoformat()
            })
        else:
            return jsonify({
                'success': True,
                'ultima_fecha_actualizacion': None
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
        
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@monitor_odoo_bp.route('/importar_facturas', methods=['POST'])
def importar_facturas():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No se proporcionó archivo'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Nombre de archivo vacío'}), 400

    try:
        UPLOAD_FOLDER = 'temp_uploads'
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        filename = secure_filename(f"temp_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        df = pd.read_excel(filepath)

        # Validación de columnas requeridas
        columnas_requeridas = [
            'Líneas de factura/Número',
            'Líneas de factura/Producto/Referencia interna',
            'Líneas de factura/Producto/Nombre',
            'Líneas de factura/Contacto/Referencia',
            'Líneas de factura/Contacto/Nombre',
            'Líneas de factura/Fecha de factura',
            'Líneas de factura/Precio unitario',
            'Líneas de factura/Cantidad',
            'Líneas de factura/Producto/Categoría del producto',
            'Líneas de factura/Estado'
        ]

        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        if columnas_faltantes:
            return jsonify({
                'success': False,
                'error': f'Faltan columnas requeridas: {", ".join(columnas_faltantes)}'
            }), 400

        # Renombrar columnas
        df = df.rename(columns={
            'Líneas de factura/Número': 'numero_factura',
            'Líneas de factura/Producto/Referencia interna': 'referencia_interna',
            'Líneas de factura/Producto/Nombre': 'nombre_producto',
            'Líneas de factura/Contacto/Referencia': 'contacto_referencia',
            'Líneas de factura/Contacto/Nombre': 'contacto_nombre',
            'Líneas de factura/Fecha de factura': 'fecha_factura',
            'Líneas de factura/Precio unitario': 'precio_unitario',
            'Líneas de factura/Cantidad': 'cantidad',
            'Líneas de factura/Producto/Categoría del producto': 'categoria_producto',
            'Líneas de factura/Estado': 'estado_factura'
        })

        df = df.where(pd.notna(df), None)

        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)

        # Obtener todos los clientes de la base de datos
        cursor.execute("SELECT clave, nombre_cliente, evac FROM clientes")
        clientes_db = cursor.fetchall()

        # Preparar estructuras para búsqueda rápida
        clientes_por_clave = {str(cliente['clave']).strip().upper(): cliente for cliente in clientes_db}
        clientes_por_nombre = {}

        # Diccionario de nombres para Multimarcas A y B
        MULTIMARCAS_GROUPS = {
            'A': {
                'DOMESTIQUE 310188',
                'WE SPORTS GROUP',
                'HUMBERTO GONZALO GUERRA FLORES',
                'ADRIAN ELIAS BONILLAS',
                'ANGELA KARINA VILLEGAS CERVANTES',
                'BLANCA ESTELA CHAVEZ VELAZQUEZ',
                'COMERCIALIZADORA MEFRUP BIKE',
                'ALDO CARLOS MALDONADO MONTOYA',
                'RC PARTNERS',
                'HUGO ENRIQUE MONDRAGON VERGARA',
                'LAURA CRISTINA GUTIERREZ CRUZ',
                'LUIS FERNANDO DE VILLACAÑA LEMUS',
                'GUILLERMO FERNANDEZ GARDUÑO',
                'FRANCISCO ALBERTO FERNANDO LUARCA JARQUIN',
                'ALAN FERNANDO RINCON MALDONADO',
                'HECTOR ENRIQUE SANCHEZ GALLO',
                'SANDRA REYES SANCHEZ',
                'MARIANO VERDUZCO MENDEZ',
                'EDUARDO DANIEL CRUZ AZCOITIA',
                'CESAR MARTINEZ MARTINEZ',
                'LUIS AUGUSTO BAAS DZIB',
                'SERGIO ORTEGA OLVERA',
                'MELQUIADES GRANDE GARCIA',
                'JORGE ALBERTO ORTIZ CUERVO'
            },
            'B': {
                'TOMAS LUNA CHAVEZ',
                'DAVID ESCUDERO CHAVEZ',
                'AARON HOSAI TORRES ESTRADA',
                'CARLOS ALBERTO TORRES ALANIS',
                'MAURICIO OLIVEROS TORRES',
                'FERNANDO JAVIER RUIZ GONZALEZ',
                'PATRICIA DEL VIVAR MONTIEL',
                'COMERCIALIZADORA CONAGUINET',
                'EDUARDO NOEL RODRIGUEZ BRAY',
                'OSCAR MAURICIO CUEVAS TELLEZ',
                'GEORGINA ZAMUDIO PANTOJA',
                'AURORA JAASIEL YEBRA SANCHEZ',
                'EDNA GRACIELA PEÑA ZARATE',
                'CICLISTAS DE SANTA FE',
                'MARCOS ANTONIO CRUZ LOPEZ',
                'ARMANDO MARIN MUÑOZ',
                'RODOLFO MARTINEZ ARIETA',
                'HECTOR GERARDO ROSAS GONZALEZ',
                'EMMANUEL HERRERA FOSTER Y NOPHAL',
                'GUILLERMO FERNANDEZ GARDUÑO',
                'JOSE EDUARDO LOPEZ BAUTISTA',
                'JAVIER RIVERA SPECIA',
                'RICARDO VALENZUELA RODRIGUEZ',
                'REINHARD STEGE RENK',
                'EDGAR ENRIQUE OSEGUERA ESPERON',
                'KASAT SERVICIOS INDUSTRIALES Y DE CONSTRUCCION'
            }
        }

        # Función de normalización de nombres
        def normalizar_nombre(nombre):
            if not nombre:
                return ""
            nombre = str(nombre).strip().upper()
            # Reemplazar variaciones comunes
            reemplazos = {
                'S. A. DE C. V.': 'SA DE CV',
                'S.A. DE C.V.': 'SA DE CV',
                'S. DE R. L. DE C. V.': 'S DE RL DE CV',
                'SAPI DE C. V.': 'SAPI DE CV',
                '&': 'Y',
                ',': '',
                '.': '',
                '-': ' ',
                '  ': ' '
            }
            for original, reemplazo in reemplazos.items():
                nombre = nombre.replace(original, reemplazo)
            # Eliminar caracteres especiales
            nombre = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in nombre)
            return ' '.join(nombre.split())

        # Función para normalizar categorías (agregar espacios después de diagonales)
        def normalizar_categoria(categoria):
            if not categoria:
                return None
            categoria = str(categoria).strip()
            # Agregar espacio después de cada diagonal si no lo tiene
            categoria = re.sub(r'/(?=\S)', '/ ', categoria)
            # También corregir casos donde pueda haber múltiples espacios
            categoria = re.sub(r'\s+', ' ', categoria)
            return categoria

        # Preprocesar nombres para búsqueda
        for cliente in clientes_db:
            nombre_normalizado = normalizar_nombre(cliente['nombre_cliente'])
            if nombre_normalizado:
                if nombre_normalizado not in clientes_por_nombre:
                    clientes_por_nombre[nombre_normalizado] = cliente
                
                # También almacenar versión sin espacios
                nombre_sin_espacios = nombre_normalizado.replace(' ', '')
                if nombre_sin_espacios and nombre_sin_espacios not in clientes_por_nombre:
                    clientes_por_nombre[nombre_sin_espacios] = cliente

        # Función para buscar EVAC
        def buscar_evac(contacto_referencia, contacto_nombre):
            # 0. Primero verificar si es un cliente Multimarcas A o B
            if contacto_nombre:
                nombre_normalizado = normalizar_nombre(contacto_nombre)
                
                # Verificar grupo A
                if nombre_normalizado in MULTIMARCAS_GROUPS['A']:
                    return "A Multimarcas"
                
                # Verificar grupo B
                if nombre_normalizado in MULTIMARCAS_GROUPS['B']:
                    return "B Multimarcas"
            
            # 1. Buscar por clave (contacto_referencia)
            if contacto_referencia:
                clave_normalizada = str(contacto_referencia).strip().upper()
                if clave_normalizada in clientes_por_clave:
                    return clientes_por_clave[clave_normalizada]['evac']
            
            # 2. Buscar por nombre si no se encontró por clave
            if contacto_nombre:
                # 2.1 Coincidencia exacta
                if nombre_normalizado in clientes_por_nombre:
                    return clientes_por_nombre[nombre_normalizado]['evac']
                
                # 2.2 Versión sin espacios
                nombre_sin_espacios = nombre_normalizado.replace(' ', '')
                if nombre_sin_espacios in clientes_por_nombre:
                    return clientes_por_nombre[nombre_sin_espacios]['evac']
                
                # 2.3 Búsqueda por palabras clave
                palabras_nombre = set(nombre_normalizado.split())
                for nombre_db, cliente_db in clientes_por_nombre.items():
                    palabras_db = set(nombre_db.split())
                    if len(palabras_nombre & palabras_db) >= 2:
                        return cliente_db['evac']
            
            return None

        # Limpiar tabla antes de insertar
        cursor.execute("TRUNCATE TABLE monitor")
        conexion.commit()

        total_insertados = 0

        for _, fila in df.iterrows():
            # Validación de fecha
            try:
                fecha = pd.to_datetime(fila['fecha_factura'], errors='coerce')
                if pd.isna(fecha) or fecha < pd.to_datetime('2025-06-10'):
                    continue
            except:
                continue

            # Filtrar facturas canceladas
            estado = str(fila['estado_factura']).strip().lower() if fila['estado_factura'] else ''
            if 'cancel' in estado or 'draft' in estado:
                continue

            # Validar categoría y normalizarla
            categoria_raw = fila['categoria_producto']
            categoria = normalizar_categoria(categoria_raw) if categoria_raw else None
            if not categoria or categoria == 'SERVICIOS':
                continue

            # Calcular valores numéricos
            try:
                precio = float(fila['precio_unitario']) if fila['precio_unitario'] else 0.0
                cantidad = int(fila['cantidad']) if fila['cantidad'] else 0
                venta_total = round((precio * cantidad) * 1.16, 2)
            except (ValueError, TypeError):
                precio, cantidad, venta_total = 0.0, 0, 0.0

            # Extraer marca y subcategoría (usando la categoría normalizada)
            marca = categoria.split('/')[0].strip() if categoria else None
            subcategoria = categoria.split('/')[1].strip() if categoria and len(categoria.split('/')) > 1 else None
            apparel = 'SI' if subcategoria and subcategoria.upper() == 'APPAREL' else 'NO'
            eride = 'SI' if categoria and 'ERIDE' in categoria.upper() else 'NO'

            # Asignar EVAC
            evac = buscar_evac(fila['contacto_referencia'], fila['contacto_nombre'])

            # Preparar valores para inserción
            valores = (
                fila['numero_factura'],
                fila['referencia_interna'],
                fila['nombre_producto'],
                fila['contacto_referencia'],
                fila['contacto_nombre'],
                fecha.strftime('%Y-%m-%d') if not pd.isna(fecha) else None,
                precio,
                cantidad,
                venta_total,
                marca,
                subcategoria,
                apparel,
                eride,
                evac,
                categoria,
                fila['estado_factura']
            )

            # Insertar en la base de datos
            sql = """
                INSERT INTO monitor (
                    numero_factura, referencia_interna, nombre_producto,
                    contacto_referencia, contacto_nombre, fecha_factura,
                    precio_unitario, cantidad, venta_total,
                    marca, subcategoria, apparel, eride, evac,
                    categoria_producto, estado_factura
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, valores)
            total_insertados += 1

        conexion.commit()
        
        try:
            zona_horaria_mexico = ZoneInfo("America/Mexico_City")
            fecha_actual = datetime.now(zona_horaria_mexico)
            cursor.execute(
                "INSERT INTO historial_actualizaciones (fecha_actualizacion) VALUES (%s)",
                (fecha_actual,)
            )
            conexion.commit() 
        except Exception as e:
            print(f"No se pudo guardar la fecha de actualización: {e}")

        cursor.close()
        os.remove(filepath)

        return jsonify({
            'success': True,
            'message': f'Se importaron {total_insertados} registros correctamente',
            'count': total_insertados
        })

    except Exception as e:
        if 'cursor' in locals():
            cursor.close()
        if 'filepath' in locals() and os.path.exists(filepath):
            os.remove(filepath)

        return jsonify({
            'success': False,
            'error': f'Ocurrió un error durante la importación: {str(e)}'
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()