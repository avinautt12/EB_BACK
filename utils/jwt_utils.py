import jwt
import datetime
from flask import request

SECRET_KEY = "121221"

def generar_token(id_usuario, rol, usuario, nombre, cliente_id, clave_cliente, nombre_cliente, id_grupo):
    payload = {
        # Datos del usuario
        'id': id_usuario,
        'rol': rol,
        'usuario': usuario,
        'nombre': nombre,
        
        # Datos del cliente
        'cliente_id': cliente_id,
        'clave': clave_cliente,
        'nombre_cliente': nombre_cliente,
        'id_grupo': id_grupo,
        
        # Expiración
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=48)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verificar_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None  # Token expirado
    except jwt.InvalidTokenError:
        return None  # Token inválido

def registrar_auditoria(cursor, accion, tabla, id_registro, descripcion):
    """
    Extrae el usuario del token actual y guarda el log en la BD.
    """
    try:
        # 1. Obtener datos del usuario desde el Request
        auth_header = request.headers.get('Authorization')
        usuario_id = None
        usuario_nombre = 'Sistema / Desconocido'

        if auth_header:
            try:
                token = auth_header.split(" ")[1]
                # REUTILIZAMOS la función verificar_token para no repetir lógica
                data = verificar_token(token)
                
                if data:
                    usuario_id = data.get('id')
                    usuario_nombre = data.get('nombre')
                else:
                    usuario_nombre = 'Token Inválido/Expirado'
            except Exception as e:
                print(f"Error procesando token en auditoría: {e}")

        # 2. Insertar en la tabla
        sql = """
            INSERT INTO auditoria_movimientos 
            (id_usuario, nombre_usuario, accion, tabla_afectada, id_registro_afectado, descripcion)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (usuario_id, usuario_nombre, accion, tabla, id_registro, descripcion))
        
        # Nota: No hacemos commit aquí, dependemos de la transacción principal.
        
    except Exception as e:
        print(f"Error registrando auditoría: {e}")