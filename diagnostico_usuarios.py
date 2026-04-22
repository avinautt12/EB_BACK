#!/usr/bin/env python3
"""
Diagnóstico: Identificar por qué faltan usuarios en la sincronización
"""
from db_conexion import obtener_conexion

conn = obtener_conexion()
cur = conn.cursor(dictionary=True)

print("\n" + "=" * 80)
print("DIAGNÓSTICO: ¿Dónde están los usuarios faltantes?")
print("=" * 80 + "\n")

# 1. Total en /usuarios/para-monitor
print("[1] Total que DEBERÍA traer /usuarios/para-monitor:")
cur.execute("""
    SELECT COUNT(*) as total FROM (
        SELECT 
            c.id AS id_cliente,
            u.id AS id_usuario,
            COALESCE(u.nombre, c.nombre_cliente) AS nombre
        FROM clientes c
        LEFT JOIN usuarios u ON u.cliente_id = c.id
        LEFT JOIN grupo_clientes g ON COALESCE(c.id_grupo, u.id_grupo) = g.id

        UNION

        SELECT
            NULL AS id_cliente,
            u.id AS id_usuario,
            u.nombre
        FROM usuarios u
        LEFT JOIN grupo_clientes g ON u.id_grupo = g.id
        WHERE u.cliente_id IS NULL
    ) as full_list
""")
total_monitor = cur.fetchone()['total']
print(f"    ✓ Total: {total_monitor}\n")

# 2. Lo que estamos capturando (con filter)
print("[2] Lo que estamos capturando (id_usuario != NULL):")
cur.execute("""
    SELECT COUNT(*) as total FROM (
        SELECT 
            c.id AS id_cliente,
            u.id AS id_usuario,
            COALESCE(u.nombre, c.nombre_cliente) AS nombre
        FROM clientes c
        LEFT JOIN usuarios u ON u.cliente_id = c.id
        LEFT JOIN grupo_clientes g ON COALESCE(c.id_grupo, u.id_grupo) = g.id

        UNION

        SELECT
            NULL AS id_cliente,
            u.id AS id_usuario,
            u.nombre
        FROM usuarios u
        LEFT JOIN grupo_clientes g ON u.id_grupo = g.id
        WHERE u.cliente_id IS NULL
    ) as full_list
    WHERE id_usuario IS NOT NULL
""")
total_capturado = cur.fetchone()['total']
print(f"    ✓ Total: {total_capturado}\n")

# 3. Lo que falta
print("[3] Lo que FALTA (clientes sin usuario):")
faltantes = total_monitor - total_capturado
print(f"    ✗ Total faltante: {faltantes}\n")

# 4. Detalles de qué son esos faltantes
print("[4] Detalles: Clientes SIN usuario vinculado")
cur.execute("""
    SELECT COUNT(*) as total
    FROM clientes c
    LEFT JOIN usuarios u ON u.cliente_id = c.id
    WHERE u.id IS NULL
""")
clientes_sin_usuario = cur.fetchone()['total']
print(f"    ✗ Clientes sin usuario: {clientes_sin_usuario}\n")

# 5. Información general
print("[5] Información general de la BD:")
cur.execute("SELECT COUNT(*) as total FROM usuarios")
total_usuarios = cur.fetchone()['total']
print(f"    • Usuarios totales: {total_usuarios}")

cur.execute("SELECT COUNT(*) as total FROM usuarios WHERE rol_id = 1")
admins = cur.fetchone()['total']
print(f"    • Administradores (rol_id=1): {admins}")

cur.execute("SELECT COUNT(*) as total FROM usuarios WHERE rol_id IS NOT NULL AND rol_id != 1")
usuarios_normales = cur.fetchone()['total']
print(f"    • Usuarios normales (rol != admin): {usuarios_normales}")

cur.execute("SELECT COUNT(*) as total FROM clientes")
total_clientes = cur.fetchone()['total']
print(f"    • Clientes totales: {total_clientes}\n")

# 6. Conclusión
print("[CONCLUSIÓN]")
print(f"────────────────────────────────────────────────────────────────────────────────")
print(f"Monitor de Pedidos debería tener:  {total_monitor} entradas")
print(f"Estamos sincronizando:             {total_capturado} (usuarios reales)")
print(f"Nos faltan:                        {faltantes} (clientes sin usuario)")
print(f"\n⚠️  El problema es que {faltantes} clientes NO tienen usuario vinculado,")
print(f"   por lo que no se puede generar OTP para ellos (no hay id_usuario).")
print(f"\n✅ Solución: Crear usuarios para esos {faltantes} clientes huérfanos.")
print("────────────────────────────────────────────────────────────────────────────────\n")

cur.close()
conn.close()
