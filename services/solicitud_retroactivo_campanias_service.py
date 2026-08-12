"""
Capa de acceso a datos (Data Access) para Solicitud de Retroactivos - Campañas.

GUÍA DEL PROYECTO:
- Este archivo contiene únicamente consultas SQL.
- Las rutas viven en:
    routes/solicitud_retroactivos_campanias.py
- Las rutas son responsables de:
    * Validaciones
    * Reglas de negocio
    * Conexión
    * Commit / rollback
    * Respuestas HTTP
- Este service únicamente:
    * Recibe un cursor ya abierto.
    * Ejecuta SQL.
    * Devuelve los resultados.

GUÍA:
La campaña contiene:
    id
    nombre
    fecha_inicio
    fecha_fin
    msi_id
    fecha_registro
    activa

Y tiene una relación de productos:
    campaña -> productos

El arreglo de productos que recibe el frontend se persiste
en una tabla de relación.

GUÍA:
No se realiza commit() ni rollback() aquí.
La transacción completa es responsabilidad de routes.

GUÍA:
fecha_registro:
- Al crear se genera automáticamente mediante DEFAULT CURRENT_TIMESTAMP.
- Al editar se actualiza automáticamente mediante
  ON UPDATE CURRENT_TIMESTAMP.

GUÍA:
activa:
    1 = campaña activa
    0 = campaña inactiva

No se elimina una campaña al desactivarla.
Para desactivarla se actualiza activa = 0.
"""


# ============================================================
# MSI
# ============================================================

def listar_msi(cursor):
    """
    Obtiene el catálogo completo de MSI.

    GUÍA:
    La información proviene de:
        solicitud_retroactivo_msi

    Este método alimenta el selector de MSI del frontend.
    """
    cursor.execute("""
        SELECT
            id,
            plazo_meses,
            porcentaje
        FROM solicitud_retroactivo_msi
        ORDER BY plazo_meses ASC
    """)
    return cursor.fetchall()


def obtener_msi_por_id(cursor, msi_id):
    """
    Obtiene un MSI específico.

    GUÍA:
    Se utiliza antes de crear o editar una campaña para comprobar
    que el msi_id recibido realmente exista.
    """
    cursor.execute("""
        SELECT
            id,
            plazo_meses,
            porcentaje
        FROM solicitud_retroactivo_msi
        WHERE id = %s
    """, (msi_id,))
    return cursor.fetchone()


# ============================================================
# PRODUCTOS
# ============================================================

def validar_productos(cursor, productos):
    """
    Comprueba qué productos existen.

    GUÍA:
    productos llega desde routes como:
        [1, 2, 3]

    El método devuelve únicamente los productos existentes.
    La ruta es responsable de comparar el resultado contra el arreglo
    original y determinar si existen IDs inválidos.

    GUÍA:
    Actualmente se utiliza la tabla:
        productos

    Si el nombre real de la tabla de productos del proyecto es otro,
    esta consulta debe cambiarse aquí y NO en routes.
    """
    if not productos:
        return []

    placeholders = ', '.join(['%s'] * len(productos))
    cursor.execute(f"""
        SELECT id
        FROM productos
        WHERE id IN ({placeholders})
    """, tuple(productos))
    
    return cursor.fetchall()


# ============================================================
# CAMPAÑAS
# ============================================================

def listar_campanias(cursor):
    """
    Obtiene todas las campañas.

    GUÍA:
    Se muestran campañas activas e inactivas.
    No se filtra:
        WHERE activa = 1
    porque el administrador necesita visualizar también las campañas
    que fueron desactivadas.

    GUÍA:
    Los productos se devuelven agrupados por campaña.
    La ruta convierte el resultado a un arreglo JSON para el frontend.
    """
    cursor.execute("""
       SELECT
        c.id,
        c.nombre,
        c.fecha_inicio,
        c.fecha_fin,
        c.msi_id,
        m.plazo_meses,
        m.porcentaje,
        c.activa,
        COALESCE(
            (
                SELECT JSON_ARRAYAGG(cp.producto_detalle_id)
                FROM solicitud_retroactivo_campania_producto_detalle cp
                WHERE cp.campania_id = c.id
            ), 
            JSON_ARRAY()
        ) AS productos
    FROM solicitud_retroactivo_campanias c
    LEFT JOIN solicitud_retroactivo_msi m
        ON m.id = c.msi_id
    ORDER BY 
        c.fecha_fin DESC;
    """)
    return cursor.fetchall()


def obtener_campania(cursor, id_campania):
    """
    Obtiene una campaña por ID.

    GUÍA:
    Este método se utiliza:
        - Para consultar una campaña individual.
        - Para comprobar que exista antes de editar.
        - Para comprobar que exista antes de eliminar.
        - Después de crear/editar para devolver el registro actualizado.

    Los productos se devuelven como arreglo JSON.
    """
    cursor.execute("""
        SELECT
            c.id,
            c.nombre,
            c.fecha_inicio,
            c.fecha_fin,
            c.msi_id,
            m.plazo_meses,
            m.porcentaje,
            c.activa,
            COALESCE(
                (
                    SELECT JSON_ARRAYAGG(cp.producto_detalle_id)
                    FROM solicitud_retroactivo_campania_producto_detalle cp
                    WHERE cp.campania_id = c.id
                ), 
                JSON_ARRAY()
            ) AS productos
        FROM solicitud_retroactivo_campanias c
        LEFT JOIN solicitud_retroactivo_msi m
            ON m.id = c.msi_id
        WHERE c.id = %s
    """, (id_campania,))
    return cursor.fetchone()


# ============================================================
# CREAR CAMPAÑA
# ============================================================

def crear_campania(cursor, nombre, fecha_inicio, fecha_fin, msi_id, activa):
    """
    Crea una campaña y devuelve el ID generado.
    
    GUÍA:
    El cursor debe ser capaz de devolver lastrowid.
    """
    cursor.execute("""
        INSERT INTO solicitud_retroactivo_campanias (
            nombre,
            fecha_inicio,
            fecha_fin,
            msi_id,
            activa
        )
        VALUES (%s, %s, %s, %s, %s)
    """, (nombre, fecha_inicio, fecha_fin, msi_id, activa))
    
    return cursor.lastrowid


# ============================================================
# EDITAR CAMPAÑA
# ============================================================

def actualizar_campania(cursor, id_campania, nombre, fecha_inicio, fecha_fin, msi_id, activa):
    """
    Actualiza los datos principales de una campaña.

    GUÍA:
    La columna debe estar configurada en BD con:
        ON UPDATE CURRENT_TIMESTAMP
    Por lo tanto, cualquier edición de la campaña actualiza
    automáticamente.
    """
    cursor.execute("""
        UPDATE solicitud_retroactivo_campanias
        SET
            nombre = %s,
            fecha_inicio = %s,
            fecha_fin = %s,
            msi_id = %s,
            activa = %s
        WHERE id = %s
    """, (nombre, fecha_inicio, fecha_fin, msi_id, activa, id_campania))


# ============================================================
# PRODUCTOS DE LA CAMPAÑA
# ============================================================

def agregar_productos_campania(cursor, id_campania, productos):
    """
    Agrega productos asociados a una campaña.

    GUÍA:
    products llega como:
        [1, 2, 3]

    Y se convierte en registros:
        campania_id | producto_id
        ------------|------------
        10          | 1
        10          | 2
        10          | 3

    IMPORTANTE:
    La ruta ya se encargó de validar que los productos existan.
    """
    if not productos:
        return

    valores = [(id_campania, producto_id) for producto_id in productos]

    cursor.executemany("""
        INSERT INTO solicitud_retroactivo_campania_producto_detalle (
            campania_id,
            producto_id
        )
        VALUES (%s, %s)
    """, valores)


def eliminar_productos_campania(cursor, id_campania):
    """
    Elimina todas las relaciones producto de una campaña.

    GUÍA:
    Al editar una campaña NO hacemos actualización individual
    de cada producto.

    Se utiliza el siguiente flujo:
        1. DELETE relaciones actuales
        2. INSERT relaciones nuevas

    Ejemplo:
        Antes:    [1, 2, 3]
        Después:  [2, 5]

        Se eliminan: 1, 2, 3
        Y se insertan: 2, 5

    Esto simplifica considerablemente el manejo del arreglo.
    """
    cursor.execute("""
        DELETE FROM solicitud_retroactivo_campania_producto_detalle
        WHERE campania_id = %s
    """, (id_campania,))


# ============================================================
# ELIMINAR CAMPAÑA
# ============================================================

def eliminar_campania(cursor, id_campania):
    """
    Elimina físicamente una campaña.

    GUÍA:
    Las relaciones de productos se eliminan primero mediante:
        eliminar_productos_campania()
    y después se elimina el registro principal.

    La ruta controla el orden y la transacción.
    """
    cursor.execute("""
        DELETE FROM solicitud_retroactivo_campanias
        WHERE id = %s
    """, (id_campania,))