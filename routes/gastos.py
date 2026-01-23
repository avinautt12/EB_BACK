from flask import Blueprint, jsonify, request
from db_conexion import obtener_conexion

# Mantenemos el mismo Blueprint
gastos_bp = Blueprint('gastos_bp', __name__, url_prefix='/flujo')

# ==============================================================================
# 1. CREAR NUEVO CONCEPTO (Agregar una fila nueva a la tabla)
# ==============================================================================
@gastos_bp.route('/conceptos', methods=['POST'])
def crear_concepto():
    data = request.get_json()
    conexion = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        
        # Insertamos en el catálogo
        sql = """
            INSERT INTO cat_conceptos (nombre_concepto, categoria, orden_reporte)
            VALUES (%s, %s, %s)
        """
        # Sugerencia: El orden podría calcularse automático, pero aquí lo pedimos manual
        cursor.execute(sql, (
            data.get('nombre'),
            data.get('categoria'), # Ej: 'Egresos Operativos'
            data.get('orden', 99)  # Por defecto al final
        ))
        conexion.commit()
        return jsonify({"mensaje": "Concepto creado correctamente"}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conexion: conexion.close()

# ==============================================================================
# 2. GUARDAR VALOR (La magia: Insertar o Actualizar Monto)
# ==============================================================================
@gastos_bp.route('/guardar-valor', methods=['POST'])
def guardar_valor():
    """
    Este endpoint sirve para:
    1. Agregar un presupuesto (Proyectado)
    2. Registrar un gasto real (Real)
    
    Recibe JSON: { 
        "id_concepto": 20, 
        "fecha": "2025-03-01", 
        "tipo": "real",  <-- o "proyectado"
        "monto": 5000.00 
    }
    """
    data = request.get_json()
    conexion = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        id_concepto = data['id_concepto']
        fecha = data['fecha']
        monto = data['monto']
        tipo = data.get('tipo', 'real') # 'real' o 'proyectado'

        # Lógica "UPSERT" (Update or Insert)
        # Verificamos si ya existe registro para ese mes y concepto
        check_sql = "SELECT id_valor FROM flujo_valores WHERE id_concepto = %s AND fecha_reporte = %s"
        cursor.execute(check_sql, (id_concepto, fecha))
        resultado = cursor.fetchone()

        if resultado:
            # SI EXISTE: Actualizamos solo la columna correspondiente
            id_valor = resultado[0] # Tuple access
            columna = "monto_real" if tipo == 'real' else "monto_proyectado"
            
            update_sql = f"UPDATE flujo_valores SET {columna} = %s WHERE id_valor = %s"
            cursor.execute(update_sql, (monto, id_valor))
        else:
            # NO EXISTE: Creamos la fila completa
            if tipo == 'real':
                insert_sql = """
                    INSERT INTO flujo_valores (id_concepto, fecha_reporte, monto_real, monto_proyectado)
                    VALUES (%s, %s, %s, 0)
                """
            else:
                insert_sql = """
                    INSERT INTO flujo_valores (id_concepto, fecha_reporte, monto_real, monto_proyectado)
                    VALUES (%s, %s, 0, %s)
                """
            cursor.execute(insert_sql, (id_concepto, fecha, monto))

        conexion.commit()
        return jsonify({"mensaje": "Valor actualizado correctamente"}), 200

    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500
    finally:
        if conexion: conexion.close()