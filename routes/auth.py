from flask import Blueprint, request, jsonify
from db_conexion import obtener_conexion
from utils.seguridad import hash_password, verificar_password
from utils.jwt_utils import generar_token
import re
import random
from utils.email import enviar_correo_activacion
from datetime import datetime, timedelta
import uuid

auth = Blueprint('auth', __name__, url_prefix='')

def campo_vacio(campo):
    return campo is None or str(campo).strip() == ''

@auth.route('/registro', methods=['POST'])
def registrar_usuario():
    # 1. VALIDACIONES SIN BASE DE DATOS (Hazlas primero, es gratis)
    data = request.get_json()
    if not data:
        return jsonify({"error": "No se proporcionaron datos"}), 400

    usuario    = data.get('usuario')
    contrasena = data.get('contrasena')
    nombre     = data.get('nombre')
    correo     = data.get('correo')
    rol        = data.get('rol', 'Usuario')
    cliente_id = data.get('cliente_id')
    id_grupo   = data.get('id_grupo')

    # Validaciones básicas de campos
    campos_requeridos = {'usuario': usuario, 'contrasena': contrasena, 'nombre': nombre, 'correo': correo}
    for campo, valor in campos_requeridos.items():
        if not valor or (isinstance(valor, str) and valor.strip() == ''):
            return jsonify({"error": f"El campo '{campo}' es obligatorio"}), 400

    if not isinstance(usuario, str) or not isinstance(contrasena, str):
        return jsonify({"error": "Usuario y contraseña cadenas de texto"}), 400

    if not re.match(r"^[a-zA-Z0-9_.-]{3,20}$", usuario):
        return jsonify({"error": "Usuario: 3-20 caracteres alfanuméricos"}), 400

    if not re.match(r"[^@]+@[^@]+\.[^@]+", correo):
        return jsonify({"error": "Correo inválido"}), 400

    if len(contrasena) < 6:
        return jsonify({"error": "Contraseña mín. 6 caracteres"}), 400

    roles_validos = {"Administrador": 1, "Usuario": 2}
    if rol not in roles_validos:
        return jsonify({"error": "Rol inválido"}), 400
    rol_id = roles_validos[rol]

    # 2. AHORA SÍ, ABRIMOS LA BASE DE DATOS
    conexion = obtener_conexion()
    cursor = None

    try:
        cursor = conexion.cursor(dictionary=True)

        # Validar cliente_id (requiere BD)
        if cliente_id not in [None, "", "null"]:
            try:
                cliente_id = int(cliente_id)
                cursor.execute("SELECT id FROM clientes WHERE id = %s", (cliente_id,))
                if not cursor.fetchone():
                    return jsonify({"error": "El cliente_id no existe"}), 400
            except ValueError:
                return jsonify({"error": "cliente_id inválido"}), 400
        else:
            cliente_id = None

        # Validar id_grupo si se proporciona (y no hay cliente_id)
        if id_grupo not in [None, '', 'null']:
            try:
                id_grupo = int(id_grupo)
                cursor.execute("SELECT id FROM grupo_clientes WHERE id = %s", (id_grupo,))
                if not cursor.fetchone():
                    return jsonify({"error": "El id_grupo no existe"}), 400
            except ValueError:
                return jsonify({"error": "id_grupo inválido"}), 400
        else:
            id_grupo = None

        # Validar duplicados (requiere BD)
        cursor.execute("SELECT id FROM usuarios WHERE usuario = %s", (usuario,))
        if cursor.fetchone():
            return jsonify({"error": "El usuario ya existe"}), 400

        cursor.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
        if cursor.fetchone():
            return jsonify({"error": "El correo ya existe"}), 400
        
        # Insertar
        contrasena_hash = hash_password(contrasena)
        # Si hay cliente_id, id_grupo viene de la tabla clientes (JOIN); si no, lo guardamos directo
        id_grupo_directo = None if cliente_id else id_grupo
        cursor.execute(
            """INSERT INTO usuarios (usuario, contrasena, nombre, correo, rol_id, activo, cliente_id, id_grupo) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (usuario, contrasena_hash, nombre, correo, rol_id, True, cliente_id, id_grupo_directo)
        )
        conexion.commit()
        nuevo_id = cursor.lastrowid

        # Obtener resultado
        cursor.execute("""
            SELECT u.id, u.usuario, u.nombre, u.correo, r.nombre AS rol, u.activo, 
                   c.nombre_cliente, c.id AS cliente_id,
                   COALESCE(c.id_grupo, u.id_grupo) AS id_grupo
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            LEFT JOIN clientes c ON u.cliente_id = c.id
            WHERE u.id = %s
        """, (nuevo_id,))
        usuario_creado = cursor.fetchone()

        return jsonify({"mensaje": "Registrado", "usuario": usuario_creado}), 201

    except Exception as e:
        if conexion.is_connected(): conexion.rollback()
        return jsonify({"error": str(e)}), 500
    
    finally:
        # 3. CERRAMOS PASE LO QUE PASE
        if cursor: cursor.close()
        if conexion and conexion.is_connected(): conexion.close()


@auth.route('/registro-integral', methods=['POST'])
def registrar_usuario_integral():
    """
    Registra un usuario vinculado a un cliente específico dentro de un grupo integral.

    Flujo:
      1. El administrador elige el grupo integral (id_grupo) y el cliente dentro del grupo (cliente_id).
      2. Se valida que ese cliente_id pertenezca realmente al grupo indicado.
      3. Se crea el usuario con ese cliente_id → el token JWT incluirá id_grupo
         automáticamente (vía la JOIN en /login).

    Body JSON requerido:
      usuario, contrasena, nombre, correo, id_grupo (int), cliente_id (int)
    Body JSON opcional:
      rol  (default: "Usuario")
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No se proporcionaron datos"}), 400

    usuario    = data.get('usuario')
    contrasena = data.get('contrasena')
    nombre     = data.get('nombre')
    correo     = data.get('correo')
    rol        = data.get('rol', 'Usuario')
    id_grupo   = data.get('id_grupo')
    cliente_id = data.get('cliente_id')

    # ── Validaciones sin BD ──────────────────────────────────────────────────
    campos_req = {'usuario': usuario, 'contrasena': contrasena,
                  'nombre': nombre, 'correo': correo}
    for campo, valor in campos_req.items():
        if not valor or (isinstance(valor, str) and valor.strip() == ''):
            return jsonify({"error": f"El campo '{campo}' es obligatorio"}), 400

    if not re.match(r"^[a-zA-Z0-9_.-]{3,20}$", usuario):
        return jsonify({"error": "Usuario: 3-20 caracteres alfanuméricos"}), 400

    if not re.match(r"[^@]+@[^@]+\.[^@]+", correo):
        return jsonify({"error": "Correo inválido"}), 400

    if len(contrasena) < 6:
        return jsonify({"error": "Contraseña mín. 6 caracteres"}), 400

    roles_validos = {"Administrador": 1, "Usuario": 2}
    if rol not in roles_validos:
        return jsonify({"error": "Rol inválido"}), 400
    rol_id = roles_validos[rol]

    if not id_grupo:
        return jsonify({"error": "id_grupo es obligatorio"}), 400

    try:
        id_grupo = int(id_grupo)
        cliente_id = int(cliente_id) if cliente_id else None
    except (ValueError, TypeError):
        return jsonify({"error": "id_grupo y cliente_id deben ser enteros"}), 400

    # ── Validaciones con BD ──────────────────────────────────────────────────
    conexion = obtener_conexion()
    cursor   = None
    try:
        cursor = conexion.cursor(dictionary=True)

        # 1. Verificar que el grupo exista
        cursor.execute("SELECT id, nombre_grupo FROM grupo_clientes WHERE id = %s", (id_grupo,))
        grupo = cursor.fetchone()
        if not grupo:
            return jsonify({"error": "El grupo integral no existe"}), 404

        # 2. Verificar que el cliente pertenezca al grupo (solo si se proporciona cliente_id)
        cliente = None
        if cliente_id:
            cursor.execute(
                "SELECT id, nombre_cliente, clave FROM clientes WHERE id = %s AND id_grupo = %s",
                (cliente_id, id_grupo)
            )
            cliente = cursor.fetchone()
            if not cliente:
                return jsonify({"error": "El cliente no pertenece al grupo indicado"}), 400

        # 3. Verificar duplicados
        cursor.execute("SELECT id FROM usuarios WHERE usuario = %s", (usuario,))
        if cursor.fetchone():
            return jsonify({"error": "El usuario ya existe"}), 400

        cursor.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
        if cursor.fetchone():
            return jsonify({"error": "El correo ya está registrado"}), 400

        # 4. Insertar usuario
        # Si no hay cliente_id, guardamos id_grupo directamente en la columna id_grupo
        contrasena_hash = hash_password(contrasena)
        cursor.execute(
            """INSERT INTO usuarios (usuario, contrasena, nombre, correo, rol_id, activo, cliente_id, id_grupo)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (usuario, contrasena_hash, nombre, correo, rol_id, True,
             cliente_id, None if cliente_id else id_grupo)
        )
        conexion.commit()
        nuevo_id = cursor.lastrowid

        # 5. Devolver el usuario creado con contexto de grupo
        cursor.execute("""
            SELECT u.id, u.usuario, u.nombre, u.correo, r.nombre AS rol, u.activo,
                   c.nombre_cliente, c.clave AS clave_cliente, c.id AS cliente_id,
                   g.id AS id_grupo, g.nombre_grupo
            FROM usuarios u
            JOIN roles r ON u.rol_id = r.id
            LEFT JOIN clientes c ON u.cliente_id = c.id
            LEFT JOIN grupo_clientes g ON COALESCE(c.id_grupo, u.id_grupo) = g.id
            WHERE u.id = %s
        """, (nuevo_id,))
        usuario_creado = cursor.fetchone()

        return jsonify({
            "mensaje": f"Usuario registrado en el grupo '{grupo['nombre_grupo']}'",
            "usuario": usuario_creado
        }), 201

    except Exception as e:
        if conexion.is_connected(): conexion.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conexion and conexion.is_connected(): conexion.close()


@auth.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data: return jsonify({"error": "Sin datos"}), 400
    usuario = data.get('usuario')
    contrasena = data.get('contrasena')
    if campo_vacio(usuario) or campo_vacio(contrasena): return jsonify({"error": "Faltan datos"}), 400

    conexion = obtener_conexion()
    cursor = None
    try:
        cursor = conexion.cursor(dictionary=True)
        # Traemos todos los campos necesarios, incluido el nuevo campo 'flujo'
        cursor.execute("""
            SELECT u.*, c.id as cliente_id, c.clave as clave_cliente, 
                   c.nombre_cliente,
                   COALESCE(c.id_grupo, u.id_grupo) AS id_grupo,
                   u.flujo 
            FROM usuarios u 
            LEFT JOIN clientes c ON u.cliente_id = c.id 
            WHERE u.usuario = %s AND u.activo = TRUE
        """, (usuario,))
        user = cursor.fetchone()
        
        if user and verificar_password(contrasena, user['contrasena']):
            # Llamada corregida con exactamente 9 argumentos
            token = generar_token(
                user['id'],             # 1
                user['rol_id'],         # 2
                user['usuario'],        # 3
                user['nombre'],          # 4
                user['cliente_id'],     # 5
                user['clave_cliente'],  # 6
                user['nombre_cliente'], # 7
                user['id_grupo'],       # 8
                user['flujo']           # 9
            )
            return jsonify({"token": token}), 200
            
        return jsonify({"error": "Credenciales incorrectas"}), 401
    except Exception as e:
        print(f"Error en login: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conexion and conexion.is_connected(): conexion.close()

@auth.route('/logout', methods=['POST'])
def logout():
    # Validación previa
    data = request.get_json()
    if not data or 'token' not in data: return jsonify({"error": "Falta token"}), 400
    token = data['token']

    # Abrir conexión
    conexion = obtener_conexion()
    cursor = None
    try:
        cursor = conexion.cursor()
        cursor.execute("UPDATE usuarios SET token = NULL WHERE token = %s", (token,))
        conexion.commit()
        return jsonify({"mensaje": "Sesión cerrada"}), 200
    except Exception as e:
        conexion.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conexion and conexion.is_connected(): conexion.close()


@auth.route('/enviar_codigo_activacion', methods=['POST'])
def enviar_codigo_activacion():
    data = request.get_json()
    correo = data.get('correo')
    if campo_vacio(correo): return jsonify({"error": "Correo obligatorio"}), 400

    conexion = obtener_conexion()
    cursor = None
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
        if not cursor.fetchone():
            return jsonify({"error": "Usuario no encontrado"}), 404 # Aquí estaba el problema antes, retornabas sin cerrar

        codigo = str(random.randint(100000, 999999))
        cursor.execute("UPDATE usuarios SET codigo_activacion = %s WHERE correo = %s", (codigo, correo))
        conexion.commit()
        
        enviar_correo_activacion(correo, codigo)
        return jsonify({"mensaje": "Código enviado"}), 200
    except Exception as e:
        conexion.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conexion and conexion.is_connected(): conexion.close()


@auth.route('/verificar_codigo', methods=['POST'])
def verificar_codigo():
    data = request.get_json()
    codigo = data.get('codigo')
    if campo_vacio(codigo): return jsonify({"error": "Código obligatorio"}), 400

    conexion = obtener_conexion()
    cursor = None
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT id FROM usuarios WHERE codigo_activacion = %s AND activo = TRUE", (codigo,))
        usuario = cursor.fetchone()

        if not usuario:
            return jsonify({"error": "Código inválido"}), 404

        token_temp = str(uuid.uuid4())
        expiracion = datetime.utcnow() + timedelta(minutes=15)
        cursor.execute("UPDATE usuarios SET codigo_activacion = NULL, token_correo = %s, token_expiracion = %s WHERE id = %s", (token_temp, expiracion, usuario['id']))
        conexion.commit()

        return jsonify({"mensaje": "Verificado", "token": token_temp}), 200
    except Exception as e:
        conexion.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conexion and conexion.is_connected(): conexion.close()


@auth.route('/cambiar_contrasena', methods=['POST'])    
def cambiar_contrasena():
    data = request.get_json()
    token = data.get('token')
    nueva = data.get('nueva_contrasena')

    if campo_vacio(token) or campo_vacio(nueva): return jsonify({"error": "Faltan datos"}), 400
    if len(nueva) < 6: return jsonify({"error": "Contraseña corta"}), 400

    conexion = obtener_conexion()
    cursor = None
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT id, token_expiracion FROM usuarios WHERE token_correo = %s", (token,))
        usuario = cursor.fetchone()

        if not usuario: return jsonify({"error": "Token inválido"}), 400
        if usuario['token_expiracion'] < datetime.utcnow(): return jsonify({"error": "Token expirado"}), 400

        hash_nueva = hash_password(nueva)
        cursor.execute("UPDATE usuarios SET contrasena = %s, token_correo = NULL, token_expiracion = NULL WHERE id = %s", (hash_nueva, usuario['id']))
        conexion.commit()

        return jsonify({"mensaje": "Contraseña actualizada"}), 200
    except Exception as e:
        conexion.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conexion and conexion.is_connected(): conexion.close()