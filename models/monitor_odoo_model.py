from db_conexion import obtener_conexion

def obtener_todos_los_registros():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM monitor_odoo")
    resultados = cursor.fetchall()
    cursor.close()
    conexion.close()
    return resultados

