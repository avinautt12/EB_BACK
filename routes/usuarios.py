from flask import Blueprint, jsonify, request
from models.user_model import obtener_usuarios
import re
import logging
from utils.seguridad import hash_password, verificar_password, generar_token
from utils.odoo_utils import get_odoo_models, ODOO_DB, ODOO_PASSWORD, ODOO_COMPANY_ID
from db_conexion import obtener_conexion

def campo_vacio(valor):
    return valor is None or (isinstance(valor, str) and valor.strip() == "")

usuarios_bp = Blueprint('usuarios', __name__, url_prefix='/usuarios')

@usuarios_bp.route('/para-monitor', methods=['GET'])
def usuarios_para_monitor():
    """Devuelve TODOS los clientes (tengan o no usuario vinculado) junto con su grupo
    para que el administrador pueda seleccionarlos en el Monitor de Pedidos."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        
        # 1. Partimos de clientes (c) y hacemos LEFT JOIN a usuarios (u)
        # 2. UNION con usuarios que no tienen cliente vinculado (admins/internos)
        cursor.execute("""
            SELECT
                c.id AS id_cliente,
                u.id AS id_usuario,
                COALESCE(u.nombre, c.nombre_cliente) AS nombre,
                u.usuario,
                u.rol_id,
                u.activo,
                c.clave,
                c.id_grupo AS id_grupo,
                g.nombre_grupo,
                CASE WHEN fp.clave_cliente IS NOT NULL THEN 1 ELSE 0 END AS tiene_proyeccion
            FROM clientes c
            LEFT JOIN usuarios u ON u.cliente_id = c.id
            LEFT JOIN grupo_clientes g ON c.id_grupo = g.id
            LEFT JOIN (SELECT DISTINCT clave_cliente FROM forecast_proyecciones) fp ON fp.clave_cliente = c.clave

            UNION

            SELECT
                NULL AS id_cliente,
                u.id AS id_usuario,
                u.nombre,
                u.usuario,
                u.rol_id,
                u.activo,
                NULL AS clave,
                NULL AS id_grupo,
                NULL AS nombre_grupo,
                0 AS tiene_proyeccion
            FROM usuarios u
            WHERE u.cliente_id IS NULL

            ORDER BY nombre
        """)
        
        filas = cursor.fetchall()
        resultado = []
        
        for f in filas:
            # Manejamos el rol de forma segura para clientes sin usuario
            if f["rol_id"] == 1:
                rol = "Administrador"
            elif f["rol_id"] is not None:
                rol = "Usuario"
            else:
                rol = "Sin Usuario" # Identificador visual útil para tu monitor

            resultado.append({
                "id": f["id_usuario"],
                "id_cliente": f["id_cliente"],
                "nombre": f["nombre"],
                "usuario": f["usuario"],
                "rol": rol,
                "activo": bool(f["activo"]) if f["activo"] is not None else False,
                "clave": f["clave"],
                "id_grupo": f["id_grupo"],
                "nombre_grupo": f["nombre_grupo"],
                "tiene_proyeccion": bool(f["tiene_proyeccion"]),
            })
            
        return jsonify(resultado), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@usuarios_bp.route('/sync-odoo', methods=['POST'])
def sync_clientes_desde_odoo():
    """
    Sincroniza partners de Odoo hacia la tabla local `clientes`.
    Solo agrega registros nuevos (por clave/ref); no modifica los existentes.
    Retorna { agregados, ya_existian, total_odoo }.
    """
    try:
        uid, models, err = get_odoo_models()
        if not uid:
            return jsonify({'error': 'No se pudo conectar a Odoo', 'detail': err}), 500

        # Partners de Odoo con customer_rank > 0 (son clientes reales)
        partners = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD,
            'res.partner', 'search_read',
            [[['customer_rank', '>', 0]]],
            {'fields': ['id', 'ref', 'name'], 'limit': 0})

        if not partners:
            return jsonify({'agregados': 0, 'ya_existian': 0, 'total_odoo': 0}), 200

        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)

        # Claves ya existentes en local
        cursor.execute("SELECT clave FROM clientes")
        claves_locales = {r['clave'].strip().upper() for r in cursor.fetchall()}

        agregados = 0
        ya_existian = 0
        actualizados = 0

        for p in partners:
            ref    = (p.get('ref') or '').strip().upper()
            nombre = (p.get('name') or '').strip().upper()
            clave_odoo = f"ODOO{p['id']}"

            if ref:
                # Partner ya tiene clave real
                if ref in claves_locales:
                    ya_existian += 1
                elif clave_odoo in claves_locales:
                    # Tenía clave temporal → actualizar a la real
                    cursor.execute(
                        "UPDATE clientes SET clave = %s, nombre_cliente = %s WHERE clave = %s",
                        (ref, nombre, clave_odoo)
                    )
                    claves_locales.discard(clave_odoo)
                    claves_locales.add(ref)
                    actualizados += 1
                else:
                    cursor.execute(
                        "INSERT IGNORE INTO clientes (clave, nombre_cliente) VALUES (%s, %s)",
                        (ref, nombre)
                    )
                    claves_locales.add(ref)
                    agregados += 1
            else:
                # Sin ref → clave temporal ODOO{id}
                if clave_odoo in claves_locales or ref in claves_locales:
                    ya_existian += 1
                    continue
                cursor.execute(
                    "INSERT IGNORE INTO clientes (clave, nombre_cliente) VALUES (%s, %s)",
                    (clave_odoo, nombre)
                )
                claves_locales.add(clave_odoo)
                agregados += 1

        conexion.commit()
        cursor.close()
        conexion.close()

        logging.info('sync-odoo: %d agregados, %d actualizados, %d ya existían', agregados, actualizados, ya_existian)
        return jsonify({
            'agregados':    agregados,
            'actualizados': actualizados,
            'ya_existian':  ya_existian,
            'total_odoo':   len(partners),
        }), 200

    except Exception as e:
        logging.exception('sync_clientes_desde_odoo error')
        return jsonify({'error': str(e)}), 500


@usuarios_bp.route('', methods=['GET'])
def listar_usuarios():
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)

        consulta = """
        SELECT 
            u.id, u.nombre, u.correo, u.usuario, u.contrasena, 
            u.activo, u.rol_id, u.cliente_id, c.nombre_cliente
        FROM 
            usuarios u
        LEFT JOIN 
            clientes c ON u.cliente_id = c.id
        """
        cursor.execute(consulta)
        usuarios = cursor.fetchall()
        usuarios_filtrados = []

        for u in usuarios:
            usuario_filtrado = {
                "id": u["id"],
                "nombre": u["nombre"],
                "correo": u["correo"],
                "usuario": u["usuario"],
                # "contrasena": u["contrasena"],  # opcional ocultar
                "activo": u["activo"],
                "rol": "Administrador" if u["rol_id"] == 1 else "Usuario",
                "cliente_id": u.get("cliente_id"),
                "cliente_nombre": u["nombre_cliente"]  # ya viene desde la consulta
            }
            usuarios_filtrados.append(usuario_filtrado)

        return jsonify(usuarios_filtrados), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()
    
def obtener_usuarios():
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)

        consulta = """
        SELECT 
            u.id, u.nombre, u.correo, u.usuario, u.contrasena, 
            u.activo, u.rol_id, u.cliente_id, c.nombre_cliente
        FROM 
            usuarios u
        LEFT JOIN 
            clientes c ON u.cliente_id = c.id
        """
        cursor.execute(consulta)
        usuarios = cursor.fetchall()

        cursor.close()
        conexion.close()

        return usuarios
    except Exception as e:
        print(f"Error al obtener usuarios: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@usuarios_bp.route('/<int:usuario_id>', methods=['PUT'])
def actualizar_usuario(usuario_id):
    data = request.get_json()

    if not data:
        return jsonify({"error": "No se proporcionaron datos"}), 400

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        # Obtener usuario existente
        cursor.execute("SELECT * FROM usuarios WHERE id = %s", (usuario_id,))
        usuario_existente = cursor.fetchone()

        if not usuario_existente:
            return jsonify({"error": "Usuario no encontrado"}), 404

        campos_actualizar = {}
        errores = []

        # Validación y actualización del nombre
        if 'nombre' in data:
            nombre = data['nombre'].strip() if data['nombre'] else ""
            if campo_vacio(nombre):
                errores.append("El nombre es obligatorio")
            else:
                if nombre != usuario_existente['nombre']:
                    cursor.execute("SELECT id FROM usuarios WHERE nombre = %s AND id != %s", (nombre, usuario_id))
                    if cursor.fetchone():
                        errores.append("El nombre ya está en uso")
                    else:
                        campos_actualizar['nombre'] = nombre

        # Validación y actualización del correo
        if 'correo' in data:
            correo = data['correo'].strip() if data['correo'] else ""
            if campo_vacio(correo):
                errores.append("El correo es obligatorio")
            elif not re.match(r"[^@]+@[^@]+\.[^@]+", correo):
                errores.append("El correo electrónico no es válido")
            else:
                if correo != usuario_existente['correo']:
                    cursor.execute("SELECT id FROM usuarios WHERE correo = %s AND id != %s", (correo, usuario_id))
                    if cursor.fetchone():
                        errores.append("El correo electrónico ya está en uso")
                    else:
                        campos_actualizar['correo'] = correo

        # Validación y actualización del usuario
        if 'usuario' in data:
            usuario = data['usuario'].strip() if data['usuario'] else ""
            if campo_vacio(usuario):
                errores.append("El nombre de usuario es obligatorio")
            elif not re.match(r"^[a-zA-Z0-9_.-]{3,20}$", usuario):
                errores.append("El nombre de usuario debe tener entre 3 y 20 caracteres alfanuméricos")
            else:
                if usuario != usuario_existente['usuario']:
                    cursor.execute("SELECT id FROM usuarios WHERE usuario = %s AND id != %s", (usuario, usuario_id))
                    if cursor.fetchone():
                        errores.append("El nombre de usuario ya está en uso")
                    else:
                        campos_actualizar['usuario'] = usuario

        # Validación y actualización del rol
        if 'rol' in data:
            rol = data['rol'].strip() if data['rol'] else ""
            if rol == "Administrador":
                rol_id = 1
            elif rol == "Usuario":
                rol_id = 2
            else:
                errores.append("Rol inválido, debe ser 'Administrador' o 'Usuario'")
            
            if rol_id != usuario_existente['rol_id']:
                campos_actualizar['rol_id'] = rol_id

        # Validación y actualización de la contraseña
        if 'contrasena' in data:
            contrasena = data['contrasena']
            if contrasena and isinstance(contrasena, str):
                if len(contrasena) < 6:
                    errores.append("La contraseña debe tener al menos 6 caracteres")
                else:
                    # Siempre actualizar la contraseña si se proporciona y es válida
                    campos_actualizar['contrasena'] = hash_password(contrasena)
            else:
                errores.append("La contraseña debe ser una cadena de texto no vacía")

        # Validación y actualización del cliente_id (opcional)
        if 'cliente_id' in data:
            cliente_id = data['cliente_id']

            if cliente_id in [None, "", "null"]:
                campos_actualizar['cliente_id'] = None
            else:
                try:
                    cliente_id = int(cliente_id)
                    cursor.execute("SELECT id FROM clientes WHERE id = %s", (cliente_id,))
                    if not cursor.fetchone():
                        errores.append("El cliente_id proporcionado no existe")
                    else:
                        campos_actualizar['cliente_id'] = cliente_id
                except ValueError:
                    errores.append("El cliente_id debe ser un número entero válido")

        # Si hay errores, retornarlos todos juntos
        if errores:
            return jsonify({"errores": errores}), 400

        # Si no hay campos para actualizar
        if not campos_actualizar:
            return jsonify({"mensaje": "No se detectaron cambios para actualizar"}), 200

        # Construir y ejecutar la consulta de actualización
        set_clause = ', '.join([f"{key} = %s" for key in campos_actualizar.keys()])
        valores = list(campos_actualizar.values())
        valores.append(usuario_id)

        query = f"UPDATE usuarios SET {set_clause} WHERE id = %s"
        cursor.execute(query, valores)
        conexion.commit()

        # Obtener los nuevos valores para emitir el evento
        campos_emitir = {
            "id": usuario_id,
            "nombre": campos_actualizar.get('nombre', usuario_existente['nombre']),
            "correo": campos_actualizar.get('correo', usuario_existente['correo']),
            "usuario": campos_actualizar.get('usuario', usuario_existente['usuario']),
            "rol": "Administrador" if campos_actualizar.get('rol_id', usuario_existente['rol_id']) == 1 else "Usuario",
            "cliente_id": campos_actualizar.get('cliente_id', usuario_existente.get('cliente_id')),
        }

        return jsonify({
            "mensaje": "Usuario actualizado con éxito",
            "campos_actualizados": list(campos_actualizar.keys())
        }), 200

    except Exception as e:
        conexion.rollback()
        return jsonify({"error": f"Error al actualizar el usuario: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()
    
@usuarios_bp.route('/<int:usuario_id>', methods=['DELETE'])
def eliminar_usuario(usuario_id):
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        # 1. Verificar si el usuario existe
        cursor.execute("SELECT * FROM usuarios WHERE id = %s", (usuario_id,))
        usuario = cursor.fetchone()

        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # 2. Validación: No permitir eliminar el último administrador
        if usuario['rol_id'] == 1:  # Si es administrador
            cursor.execute("""
                SELECT COUNT(*) as total_admins 
                FROM usuarios 
                WHERE rol_id = 1 AND id != %s
            """, (usuario_id,))
            
            otros_admins = cursor.fetchone()['total_admins']
            
            if otros_admins == 0:
                return jsonify({
                    "error": "No se puede eliminar al último administrador"
                }), 400

        # 3. Eliminación física (PERMANENTE)
        cursor.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
        conexion.commit()  # Confirmar la transacción

        return jsonify({
            "mensaje": "Usuario eliminado permanentemente de la base de datos",
        }), 200

    except Exception as e:
        conexion.rollback()  # Revertir en caso de error
        return jsonify({
            "error": f"Error al eliminar el usuario: {str(e)}"
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()