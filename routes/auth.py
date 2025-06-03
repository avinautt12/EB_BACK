from flask import Blueprint, request, jsonify
from db_conexion import obtener_conexion
from utils.seguridad import hash_password, verificar_password, generar_token
import re

conexion = obtener_conexion()
auth = Blueprint('auth', __name__, url_prefix='')

def campo_vacio(campo):
    return campo is None or str(campo).strip() == ''

@auth.route('/registro', methods=['POST'])
def registrar_usuario():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No se proporcionaron datos"}), 400

    usuario = data.get('usuario')
    contrasena = data.get('contrasena')
    rol_id = data.get('rol_id', 2)

    if campo_vacio(usuario) or campo_vacio(contrasena):
        return jsonify({"error": "Usuario y contraseña son obligatorios"}), 400

    if not isinstance(usuario, str) or not isinstance(contrasena, str):
        return jsonify({"error": "Usuario y contraseña deben ser cadenas de texto"}), 400

    if not re.match(r"^[a-zA-Z0-9_.-]{3,20}$", usuario):
        return jsonify({"error": "El nombre de usuario debe tener entre 3 y 20 caracteres alfanuméricos"}), 400

    if len(contrasena) < 6:
        return jsonify({"error": "La contraseña debe tener al menos 6 caracteres"}), 400

    cursor = conexion.cursor(dictionary=True)

    cursor.execute("SELECT id FROM usuarios WHERE usuario = %s", (usuario,))
    if cursor.fetchone():
        return jsonify({"error": "El nombre de usuario ya está en uso"}), 400

    contrasena_hash = hash_password(contrasena)

    try:
        cursor.execute(
            "INSERT INTO usuarios (usuario, contrasena, rol_id, activo) VALUES (%s, %s, %s, %s)",
            (usuario, contrasena_hash, rol_id, True)
        )
        conexion.commit()
        return jsonify({"mensaje": "Usuario registrado con éxito"}), 201
    except Exception as e:
        conexion.rollback()
        return jsonify({"error": f"Error al registrar el usuario: {str(e)}"}), 500

@auth.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No se proporcionaron datos"}), 400

    usuario = data.get('usuario')
    contrasena = data.get('contrasena')

    if campo_vacio(usuario) or campo_vacio(contrasena):
        return jsonify({"error": "Usuario y contraseña son obligatorios"}), 400

    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM usuarios WHERE usuario = %s AND activo = TRUE", (usuario,))
        user = cursor.fetchone()
    except Exception as e:
        return jsonify({"error": f"Error en la consulta: {str(e)}"}), 500

    if user and verificar_password(contrasena, user['contrasena']):
        token = generar_token(user['id'])
        return jsonify({"token": token}), 200
    else:
        return jsonify({"error": "Credenciales incorrectas"}), 401

@auth.route('/logout', methods=['POST'])
def logout():
    data = request.get_json()

    if not data or 'token' not in data:
        return jsonify({"error": "Token no proporcionado"}), 400

    token = data['token']

    cursor = conexion.cursor()
    try:
        cursor.execute("UPDATE usuarios SET token = NULL WHERE token = %s", (token,))
        conexion.commit()
        return jsonify({"mensaje": "Sesión cerrada con éxito"}), 200
    except Exception as e:
        conexion.rollback()
        return jsonify({"error": f"Error al cerrar sesión: {str(e)}"}), 500
    

@auth.route('/cambiar_contrasena', methods=['POST'])    
def cambiar_contrasena():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No se proporcionaron datos"}), 400

    usuario = data.get('usuario')
    contrasena_actual = data.get('contrasena_actual')
    nueva_contrasena = data.get('nueva_contrasena')

    if campo_vacio(usuario) or campo_vacio(contrasena_actual) or campo_vacio(nueva_contrasena):
        return jsonify({"error": "Usuario, contraseña actual y nueva contraseña son obligatorios"}), 400

    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM usuarios WHERE usuario = %s AND activo = TRUE", (usuario,))
        user = cursor.fetchone()
    except Exception as e:
        return jsonify({"error": f"Error en la consulta: {str(e)}"}), 500

    if user and verificar_password(contrasena_actual, user['contrasena']):
        nueva_contrasena_hash = hash_password(nueva_contrasena)
        try:
            cursor.execute(
                "UPDATE usuarios SET contrasena = %s WHERE id = %s",
                (nueva_contrasena_hash, user['id'])
            )
            conexion.commit()
            return jsonify({"mensaje": "Contraseña cambiada con éxito"}), 200
        except Exception as e:
            conexion.rollback()
            return jsonify({"error": f"Error al cambiar la contraseña: {str(e)}"}), 500
    else:
        return jsonify({"error": "Credenciales incorrectas"}), 401
     