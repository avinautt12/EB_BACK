from db_conexion import obtener_conexion

def obtener_usuario_por_credenciales(usuario, contrasena):
    conn = obtener_conexion()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT * FROM usuarios 
        WHERE usuario = %s AND contrasena = %s AND activo = TRUE
    """
    cursor.execute(query, (usuario, contrasena))
    return cursor.fetchone()

def guardar_token_usuario(id_usuario, token):
    conn = obtener_conexion()
    cursor = conn.cursor()
    query = "UPDATE usuarios SET token = %s WHERE id = %s"
    cursor.execute(query, (token, id_usuario))
    conn.commit()

def obtener_usuarios():
    conn = obtener_conexion()
    cursor = conn.cursor(dictionary=True)
    query = "SELECT * FROM usuarios"
    cursor.execute(query)
    return cursor.fetchall()