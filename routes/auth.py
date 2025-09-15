from flask import Blueprint, request, jsonify
from db_conexion import obtener_conexion
from utils.seguridad import hash_password, verificar_password
from utils.jwt_utils import generar_token
import re
from socket_instance import socketio 
import random
from utils.email import enviar_correo_activacion
from datetime import datetime, timedelta
import uuid

conexion = obtener_conexion()
auth = Blueprint('auth', __name__, url_prefix='')

def campo_vacio(campo):
    return campo is None or str(campo).strip() == ''

@auth.route('/registro', methods=['POST'])
def registrar_usuario():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No se proporcionaron datos"}), 400

    # Obtener campos del JSON
    usuario = data.get('usuario')
    contrasena = data.get('contrasena')
    nombre = data.get('nombre')
    correo = data.get('correo')
    rol = data.get('rol', 'Usuario')
    cliente_id = data.get('cliente_id')

    # Validaciones básicas
    campos_requeridos = {
        'usuario': usuario,
        'contrasena': contrasena,
        'nombre': nombre,
        'correo': correo
    }
    
    for campo, valor in campos_requeridos.items():
        if not valor or (isinstance(valor, str) and valor.strip() == ''):
            return jsonify({"error": f"El campo '{campo}' es obligatorio"}), 400

    if not isinstance(usuario, str) or not isinstance(contrasena, str):
        return jsonify({"error": "Usuario y contraseña deben ser cadenas de texto"}), 400

    if not re.match(r"^[a-zA-Z0-9_.-]{3,20}$", usuario):
        return jsonify({"error": "El nombre de usuario debe tener entre 3 y 20 caracteres alfanuméricos"}), 400

    if not re.match(r"[^@]+@[^@]+\.[^@]+", correo):
        return jsonify({"error": "El correo electrónico no es válido"}), 400

    if len(contrasena) < 6:
        return jsonify({"error": "La contraseña debe tener al menos 6 caracteres"}), 400

    # Validar y traducir el rol
    roles_validos = {"Administrador": 1, "Usuario": 2}
    if rol not in roles_validos:
        return jsonify({"error": "Rol inválido, debe ser 'Administrador' o 'Usuario'"}), 400
    
    rol_id = roles_validos[rol]

    cursor = conexion.cursor(dictionary=True)

    # Validar cliente_id si se proporciona
    if cliente_id not in [None, "", "null"]:
        try:
            cliente_id = int(cliente_id)
            cursor.execute("SELECT id FROM clientes WHERE id = %s", (cliente_id,))
            if not cursor.fetchone():
                return jsonify({"error": "El cliente_id proporcionado no existe"}), 400
        except ValueError:
            return jsonify({"error": "El cliente_id debe ser un número válido"}), 400
    else:
        cliente_id = None

    # Validar unicidad de usuario, correo y nombre
    cursor.execute("SELECT id FROM usuarios WHERE usuario = %s", (usuario,))
    if cursor.fetchone():
        return jsonify({"error": "El nombre de usuario ya está en uso"}), 400

    cursor.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
    if cursor.fetchone():
        return jsonify({"error": "El correo electrónico ya está en uso"}), 400

    cursor.execute("SELECT id FROM usuarios WHERE nombre = %s", (nombre,))
    if cursor.fetchone():
        return jsonify({"error": "El nombre ya está en uso"}), 400

    # Hashear la contraseña
    contrasena_hash = hash_password(contrasena)

    # Insertar usuario
    try:
        cursor.execute(
            """
            INSERT INTO usuarios (
                usuario, contrasena, nombre, correo,
                rol_id, activo, cliente_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (usuario, contrasena_hash, nombre, correo, rol_id, True, cliente_id)
        )
        conexion.commit()
        nuevo_id = cursor.lastrowid

        # Obtener datos del usuario recién creado
        cursor.execute("""
            SELECT
                u.id,
                u.usuario,
                u.nombre,
                u.correo,
                r.nombre AS rol,
                u.activo,
                c.nombre_cliente AS cliente_nombre,
                c.id AS cliente_id
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            LEFT JOIN clientes c ON u.cliente_id = c.id
            WHERE u.id = %s
        """, (nuevo_id,))
        usuario_creado = cursor.fetchone()
        cursor.close()

        return jsonify({
            "mensaje": "Usuario registrado con éxito",
            "usuario": usuario_creado
        }), 201

    except Exception as e:
        conexion.rollback()
        return jsonify({"error": f"Error al registrar el usuario: {str(e)}"}), 500
    
    finally:
        # ESTO ES OBLIGATORIO Y SE EJECUTA SIEMPRE
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@auth.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No se proporcionaron datos"}), 400

    usuario = data.get('usuario')
    contrasena = data.get('contrasena')

    if campo_vacio(usuario) or campo_vacio(contrasena):
        return jsonify({"error": "Usuario y contraseña son obligatorios"}), 400

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    try:
        # Agregar logging para ver qué usuario se está buscando
        print(f"Intentando login para usuario: {usuario}")
        
        query = """
        SELECT u.*, c.id as cliente_id, c.clave as clave_cliente, c.nombre_cliente 
        FROM usuarios u 
        LEFT JOIN clientes c ON u.cliente_id = c.id 
        WHERE u.usuario = %s AND u.activo = TRUE
        """
        cursor.execute(query, (usuario,))
        user = cursor.fetchone()
        
        # Agregar logging para ver qué usuario se encontró
        print(f"Usuario encontrado en BD: {user}")
        
        if user:
            # Agregar logging para ver la contraseña almacenada
            print(f"Contraseña almacenada (hash): {user['contrasena']}")
            print(f"Intentando verificar contraseña para usuario: {usuario}")
            
            # Verificar la contraseña con más logging
            password_match = verificar_password(contrasena, user['contrasena'])
            print(f"Resultado de verificación de contraseña: {password_match}")
            
            if password_match:
                token = generar_token(
                    user['id'],
                    user['rol_id'],
                    user['usuario'],
                    user['nombre'],
                    user['cliente_id'],          
                    user['clave_cliente'],     
                    user['nombre_cliente']
                )
                return jsonify({
                    "token": token
                }), 200

        return jsonify({"error": "Credenciales incorrectas. Verifica tu correo o contraseña."}), 401
        
    except Exception as e:
        print(f"Error durante el login: {str(e)}")
        return jsonify({"error": f"Error en la consulta: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

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
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@auth.route('/enviar_codigo_activacion', methods=['POST'])
def enviar_codigo_activacion():
    data = request.get_json()
    correo = data.get('correo')

    if campo_vacio(correo):
        return jsonify({"error": "El correo es obligatorio"}), 400

    cursor = conexion.cursor(dictionary=True)

    cursor.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
    usuario = cursor.fetchone()

    if not usuario:
        return jsonify({"error": "No se encontró un usuario con ese correo"}), 404

    codigo = str(random.randint(100000, 999999))

    try:
        cursor.execute("UPDATE usuarios SET codigo_activacion = %s WHERE correo = %s", (codigo, correo))
        conexion.commit()

        enviar_correo_activacion(correo, codigo)

        return jsonify({"mensaje": "Código de activación enviado al correo"}), 200
    except Exception as e:
        conexion.rollback()
        return jsonify({"error": f"Error al generar el código: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@auth.route('/verificar_codigo', methods=['POST'])
def verificar_codigo():
    data = request.get_json()
    codigo_ingresado = data.get('codigo')

    if campo_vacio(codigo_ingresado):
        return jsonify({"error": "El código es obligatorio"}), 400

    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT id FROM usuarios WHERE codigo_activacion = %s AND activo = TRUE", (codigo_ingresado,))
    usuario = cursor.fetchone()

    if not usuario:
        return jsonify({"error": "Código inválido o no encontrado"}), 404

    try:
        token_temp = str(uuid.uuid4())
        expiracion = datetime.utcnow() + timedelta(minutes=15)

        cursor.execute(
            "UPDATE usuarios SET codigo_activacion = NULL, token_correo = %s, token_expiracion = %s WHERE id = %s",
            (token_temp, expiracion, usuario['id'])
        )
        conexion.commit()

        return jsonify({"mensaje": "Código verificado con éxito", "token": token_temp}), 200
    except Exception as e:
        conexion.rollback()
        return jsonify({"error": f"Error en el proceso: {str(e)}"}), 500  
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@auth.route('/cambiar_contrasena', methods=['POST'])    
def cambiar_contrasena():
    data = request.get_json()
    token = data.get('token')
    nueva_contrasena = data.get('nueva_contrasena')

    if campo_vacio(token) or campo_vacio(nueva_contrasena):
        return jsonify({"error": "Token y nueva contraseña son obligatorios"}), 400

    if len(nueva_contrasena) < 6:
        return jsonify({"error": "La nueva contraseña debe tener al menos 6 caracteres"}), 400

    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, token_expiracion FROM usuarios WHERE token_correo = %s", (token,))
        usuario = cursor.fetchone()

        if not usuario:
            return jsonify({"error": "Token inválido"}), 400

        if usuario['token_expiracion'] < datetime.utcnow():
            return jsonify({"error": "Token expirado"}), 400

        nueva_contrasena_hash = hash_password(nueva_contrasena)

        cursor.execute(
            "UPDATE usuarios SET contrasena = %s, token_correo = NULL, token_expiracion = NULL WHERE id = %s",
            (nueva_contrasena_hash, usuario['id'])
        )
        conexion.commit()

        return jsonify({"mensaje": "Contraseña cambiada con éxito"}), 200
    except Exception as e:
        conexion.rollback()
        return jsonify({"error": f"Error al cambiar la contraseña: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()
