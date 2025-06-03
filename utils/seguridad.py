import hashlib
import jwt
import datetime

SECRET_KEY = "121221"  

def hash_password(contrasena):
    return hashlib.sha256(contrasena.encode()).hexdigest()

def verificar_password(contrasena, hash_guardado):
    return hash_password(contrasena) == hash_guardado

def generar_token(usuario_id):
    payload = {
        "usuario_id": usuario_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=6)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
