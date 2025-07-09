from db_conexion import obtener_conexion
from datetime import datetime, date

def obtener_todos_los_registros():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM monitor_odoo")
    resultados = cursor.fetchall()
    cursor.close()

    for fila in resultados:
        fecha = fila.get('fecha_factura')
        if isinstance(fecha, (datetime, date)):
            fila['fecha_factura'] = fecha.strftime('%Y-%m-%d')
        elif isinstance(fecha, str) and 'GMT' in fecha:
            try:
                # Convierte fecha tipo "Mon, 30 Jun 2025 00:00:00 GMT" a "2025-06-30"
                fecha_obj = datetime.strptime(fecha, '%a, %d %b %Y %H:%M:%S %Z')
                fila['fecha_factura'] = fecha_obj.strftime('%Y-%m-%d')
            except:
                pass  # Deja la fecha como está si falla

    return resultados
    return resultados

