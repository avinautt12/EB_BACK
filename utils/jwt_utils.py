import jwt
import datetime

SECRET_KEY = "tu_clave_super_secreta"

def generar_token(id_usuario, rol):
    payload = {
        'id': id_usuario,
        'rol': rol,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verificar_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
