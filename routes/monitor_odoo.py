from flask import Blueprint, request, jsonify
import pandas as pd
from db_conexion import obtener_conexion
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from models.monitor_odoo_model import obtener_todos_los_registros

monitor_odoo_bp = Blueprint('monitor_odoo', __name__, url_prefix='')

@monitor_odoo_bp.route('/monitor_odoo', methods=['GET'])
def listar():
    datos = obtener_todos_los_registros()
    return jsonify(datos)

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

        columnas_requeridas = [
            'Líneas de factura/Número',
            'Líneas de factura/Producto/Referencia interna',
            'Líneas de factura/Producto/Nombre',
            'Contacto/Comprador',
            'Líneas de factura/Contacto/Referencia',
            'Líneas de factura/Contacto/Nombre',
            'Valor depreciable',
            'Contacto/Addenda',
            'Líneas de factura/Fecha de factura',
            'Líneas de factura/Precio unitario',
            'Líneas de factura/Cantidad',
            'Líneas de factura/Producto/Categoría del producto',
            'Líneas de factura/Estado',
        ]
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        if columnas_faltantes:
            return jsonify({
                'success': False,
                'error': f'Faltan columnas requeridas: {", ".join(columnas_faltantes)}'
            }), 400

        # Renombrar columnas base
        df = df.rename(columns={
            'Líneas de factura/Número': 'numero_factura',
            'Líneas de factura/Producto/Referencia interna': 'referencia_interna',
            'Líneas de factura/Producto/Nombre': 'nombre_producto',
            'Contacto/Comprador': 'comprador',
            'Líneas de factura/Contacto/Referencia': 'contacto_referencia',
            'Líneas de factura/Contacto/Nombre': 'contacto_nombre',
            'Valor depreciable': 'valor_depreciable',
            'Contacto/Addenda': 'addenda',
            'Líneas de factura/Fecha de factura': 'fecha_factura',
            'Líneas de factura/Precio unitario': 'precio_unitario',
            'Líneas de factura/Cantidad': 'cantidad',
            'Líneas de factura/Producto/Categoría del producto': 'categoria_producto',
            'Líneas de factura/Estado': 'estado_factura',
        })

        # Columnas opcionales
        df['costo_producto'] = df['Líneas de factura/Producto/Costo'] if 'Líneas de factura/Producto/Costo' in df.columns else None
        df['venta_total'] = df['Venta Total'] if 'Venta Total' in df.columns else None
        df['marca'] = df['Marca'] if 'Marca' in df.columns else None
        df['subcategoria'] = df['Subcategoria'] if 'Subcategoria' in df.columns else None

        # ERIDE y APPAREL
        if 'ERIDE' in df.columns:
            df['eride'] = df['ERIDE'].fillna('NO').apply(lambda x: 'SI' if str(x).strip().upper() == 'SI' else 'NO')
        else:
            df['eride'] = df['categoria_producto'].apply(lambda x: 'SI' if isinstance(x, str) and 'ERIDE' in x.upper() else 'NO')

        if 'APPAREL' in df.columns:
            df['apparel'] = df['APPAREL'].fillna('NO').apply(lambda x: 'SI' if str(x).strip().upper() == 'SI' else 'NO')
        else:
            df['apparel'] = df['categoria_producto'].apply(lambda x: 'SI' if isinstance(x, str) and 'APPAREL' in x.upper() else 'NO')

        df = df.where(pd.notna(df), None)

        def clean_for_sql(val):
            if val is None:
                return None
            if isinstance(val, float) and pd.isna(val):
                return None
            if isinstance(val, str):
                val = val.strip()
                if val.lower() == 'nan' or val == '':
                    return None
            return val

        def safe_decimal(value):
            try:
                if pd.isna(value) or value is None:
                    return None
                return float(value)
            except (ValueError, TypeError):
                return None

        conexion = obtener_conexion()
        cursor = conexion.cursor()

        # Borrar solo datos posteriores a 2025-02-01
        cursor.execute("DELETE FROM monitor_odoo WHERE fecha_factura >= '2025-02-01'")

        total_insertados = 0
        for _, fila in df.iterrows():
            try:
                cantidad = int(fila['cantidad']) if fila['cantidad'] is not None else 0
            except:
                cantidad = 0

            fecha = None
            if fila['fecha_factura'] is not None:
                try:
                    fecha_dt = pd.to_datetime(fila['fecha_factura'], errors='coerce')
                    if pd.notna(fecha_dt):
                        fecha = fecha_dt.strftime('%Y-%m-%d')
                except:
                    fecha = None

            valores_raw = [
                fila['numero_factura'], fila['referencia_interna'], fila['nombre_producto'], fila['comprador'],
                fila['contacto_referencia'], fila['contacto_nombre'], safe_decimal(fila['valor_depreciable']), fila['addenda'],
                fecha, safe_decimal(fila['precio_unitario']), cantidad,
                fila['categoria_producto'], fila['estado_factura'], safe_decimal(fila.get('costo_producto')),
                fila['eride'], fila['apparel'], safe_decimal(fila.get('venta_total')),
                clean_for_sql(fila.get('marca')), clean_for_sql(fila.get('subcategoria'))
            ]
            valores = tuple(clean_for_sql(v) for v in valores_raw)

            sql = """
                INSERT INTO monitor_odoo (
                    numero_factura, referencia_interna, nombre_producto, comprador,
                    contacto_referencia, contacto_nombre, valor_depreciable, addenda,
                    fecha_factura, precio_unitario, cantidad, categoria_producto,
                    estado_factura, costo_producto, eride, apparel, venta_total, marca, subcategoria
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            cursor.execute(sql, valores)
            total_insertados += 1

        conexion.commit()
        cursor.close()
        os.remove(filepath)

        return jsonify({
            'success': True,
            'message': f'Se importaron {total_insertados} registros correctamente',
            'count': total_insertados
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ocurrió un error durante la importación: {str(e)}'
        }), 500

