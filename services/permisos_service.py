# services/permisos_service.py
from db_conexion import obtener_conexion
from services.usuarios_hijos_service import UsuariosHijosService

class PermisosService:

    @staticmethod
    def obtener_permisos_delegables(padre_id):
        """Obtiene ÚNICAMENTE los módulos y acciones activos con la jerarquía del padre."""
        conn = obtener_conexion()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute("""
                SELECT 
                    m.id AS modulo_id,
                    m.nombre AS modulo,
                    m.identificador,
                    IF(m.padre_id IS NULL OR m.padre_id = 0, 1, 0) AS es_raiz,
                    m.padre_id,
                    p.identificador AS padre_identificador,
                    a.id AS accion_id,
                    a.nombre AS accion,
                    a.identificador AS accion_id_texto
                FROM permisos_delegables pd
                INNER JOIN modulos m ON pd.modulo_id = m.id
                LEFT JOIN modulos p ON m.padre_id = p.id
                INNER JOIN acciones a ON pd.accion_id = a.id
                WHERE pd.administrador_id = %s
                  AND m.activo = 1
                  AND a.activo = 1
            """, (padre_id,))
            return cur.fetchall()
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def obtener_permisos_usuario(padre_id, hijo_id):
        """Obtiene los permisos asignados a un usuario hijo con su módulo padre."""
        conn = obtener_conexion()
        cur = conn.cursor(dictionary=True)
        try:
            # 1. Verificar si quien consulta es SuperAdmin (Rol 1)
            cur.execute("SELECT rol_id FROM usuarios WHERE id = %s", (padre_id,))
            admin_res = cur.fetchone()
            es_super_admin = admin_res and admin_res.get('rol_id') == 1

            # 2. Si no es SuperAdmin, validar pertenencia
            if not es_super_admin:
                if not UsuariosHijosService.validar_pertenencia_hijo(padre_id, hijo_id):
                    raise Exception("Acceso denegado: Este usuario no pertenece a su ámbito de administración.")

            # 3. Consultar permisos con JOIN al módulo padre
            cur.execute("""
                SELECT 
                    up.modulo_id,
                    m.nombre AS modulo,
                    m.identificador,
                    m.padre_id,
                    p.identificador AS padre_identificador,
                    up.accion_id,
                    a.nombre AS accion,
                    a.identificador AS accion_id_texto
                FROM usuario_permisos up
                INNER JOIN modulos m ON up.modulo_id = m.id
                LEFT JOIN modulos p ON m.padre_id = p.id
                INNER JOIN acciones a ON up.accion_id = a.id
                WHERE up.usuario_id = %s
            """, (hijo_id,))
            return cur.fetchall()
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def asignar_permiso_hijo(padre_id, hijo_id, modulo_id, accion_id):
        if not UsuariosHijosService.validar_pertenencia_hijo(padre_id, hijo_id):
            raise Exception("Acceso denegado: Este usuario no pertenece a su ámbito de administración.")
        conn = obtener_conexion()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT 1 FROM permisos_delegables 
                WHERE administrador_id = %s AND modulo_id = %s AND accion_id = %s
            """, (padre_id, modulo_id, accion_id))
            if not cur.fetchone():
                raise Exception("Operación no permitida: No tiene autorización para delegar este permiso.")

            cur.execute("""
                INSERT IGNORE INTO usuario_permisos (usuario_id, modulo_id, accion_id)
                VALUES (%s, %s, %s)
            """, (hijo_id, modulo_id, accion_id))
            conn.commit()
            return {"mensaje": "Permiso asignado correctamente al usuario hijo."}
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def revocar_permiso_hijo(padre_id, hijo_id, modulo_id, accion_id):
        if not UsuariosHijosService.validar_pertenencia_hijo(padre_id, hijo_id):
            raise Exception("Acceso denegado: Este usuario no pertenece a su ámbito de administración.")
        conn = obtener_conexion()
        cur = conn.cursor()
        try:
            cur.execute("""
                DELETE FROM usuario_permisos 
                WHERE usuario_id = %s AND modulo_id = %s AND accion_id = %s
            """, (hijo_id, modulo_id, accion_id))
            conn.commit()
            return {"mensaje": "Permiso revocado correctamente."}
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()