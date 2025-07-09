import jwt
import datetime

SECRET_KEY = "123456"

def generar_token(id_usuario, rol, usuario, nombre):
    payload = {
        'id': id_usuario,
        'rol': rol,
        'usuario': usuario,
        'nombre': nombre,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=3)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verificar_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None  # Token expirado
    except jwt.InvalidTokenError:
        return None  # Token inválido

