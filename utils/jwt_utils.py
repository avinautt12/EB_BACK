import jwt
import datetime

SECRET_KEY = "123456"

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
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verificar_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None  # Token expirado
    except jwt.InvalidTokenError:
        return None  # Token inválido

