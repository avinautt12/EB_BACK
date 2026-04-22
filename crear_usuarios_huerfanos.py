#!/usr/bin/env python3
"""
Script: AUTO-CREAR USUARIOS PARA CLIENTES HUÉRFANOS

Problema: Hay 74 clientes sin usuario vinculado.
Solución: Crear automáticamente un usuario para cada cliente.
Resultado: Todos los 100+ usuarios quedarán sincronizados en Tokens de Edición.
"""

from db_conexion import obtener_conexion
from utils.seguridad import hash_password
from utils.otp_utils import sincronizar_usuarios_desde_monitor
import sys

def crear_usuarios_para_clientes_huerfanos():
    """
    Crea automáticamente usuarios para todos los clientes sin usuario vinculado.
    """
    conn = obtener_conexion()
    cur = conn.cursor(dictionary=True)
    
    print("\n" + "="*80)
    print("PASO 1: IDENTIFICAR CLIENTES SIN USUARIO")
    print("="*80)
    
    # Obtener clientes sin usuario
    cur.execute("""
        SELECT c.id, c.nombre_cliente, c.clave, c.id_grupo
        FROM clientes c
        LEFT JOIN usuarios u ON u.cliente_id = c.id
        WHERE u.id IS NULL
        ORDER BY c.nombre_cliente
    """)
    
    clientes_sin_usuario = cur.fetchall()
    print(f"\n✓ Encontrados {len(clientes_sin_usuario)} clientes sin usuario\n")
    
    if len(clientes_sin_usuario) == 0:
        print("✅ No hay clientes sin usuario. ¡Todo está sincronizado!")
        return 0
    
    # Mostrar algunos ejemplos
    print("Primeros 5 clientes a procesar:")
    for i, c in enumerate(clientes_sin_usuario[:5], 1):
        print(f"  {i}. {c['nombre_cliente']} (Clave: {c['clave']})")
    if len(clientes_sin_usuario) > 5:
        print(f"  ... y {len(clientes_sin_usuario) - 5} más")
    
    print("\n" + "="*80)
    print("PASO 2: CREAR USUARIOS AUTOMÁTICAMENTE")
    print("="*80 + "\n")
    
    creados = 0
    errores = 0
    
    for cliente in clientes_sin_usuario:
        try:
            cliente_id = cliente['id']
            nombre_cliente = cliente['nombre_cliente']
            clave = cliente['clave']
            id_grupo = cliente['id_grupo']
            
            # Generar usuario único basado en clave
            usuario = clave.lower().replace(" ", "_") if clave else f"cli_{cliente_id}"
            
            # Contraseña temporal
            contraseña_temporal = f"Temporal_{cliente_id}!2026"
            contraseña_hash = hash_password(contraseña_temporal)
            
            # Insertar usuario
            cur.execute("""
                INSERT INTO usuarios (
                    nombre,
                    usuario,
                    contrasena,
                    cliente_id,
                    rol_id,
                    activo,
                    id_grupo
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                nombre_cliente,
                usuario,
                contraseña_hash,
                cliente_id,
                2,  # rol_id = usuario normal (no admin)
                1,  # activo = sí
                id_grupo
            ))
            
            creados += 1
            
            if creados % 10 == 0 or creados == len(clientes_sin_usuario):
                print(f"  Creados: {creados}/{len(clientes_sin_usuario)} usuarios...")
            
        except Exception as e:
            errores += 1
            print(f"  ❌ Error con {cliente['nombre_cliente']}: {str(e)[:50]}")
    
    conn.commit()
    
    print(f"\n✅ Usuarios creados exitosamente: {creados}")
    if errores > 0:
        print(f"⚠️  Errores: {errores}")
    
    cur.close()
    conn.close()
    
    return creados


def verificar_resultado():
    """
    Verifica que todos los clientes ahora tienen usuario.
    """
    conn = obtener_conexion()
    cur = conn.cursor(dictionary=True)
    
    print("\n" + "="*80)
    print("PASO 3: VERIFICACIÓN")
    print("="*80)
    
    # Contar usuarios finales
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
    
    total_sincronizable = cur.fetchone()['total']
    
    print(f"\nUsuarios sincronizables: {total_sincronizable}")
    
    # Contar clientes sin usuario (debe ser 0)
    cur.execute("""
        SELECT COUNT(*) as total
        FROM clientes c
        LEFT JOIN usuarios u ON u.cliente_id = c.id
        WHERE u.id IS NULL
    """)
    
    clientes_sin_usuario = cur.fetchone()['total']
    
    print(f"Clientes sin usuario: {clientes_sin_usuario}")
    
    if clientes_sin_usuario == 0:
        print("\n✅ ¡PERFECTO! Todos los clientes tienen usuario.")
    else:
        print(f"\n⚠️  Aún hay {clientes_sin_usuario} clientes sin usuario.")
    
    cur.close()
    conn.close()
    
    return total_sincronizable


def main():
    print("\n╔════════════════════════════════════════════════════════════════════════════════╗")
    print("║  AUTO-CREAR USUARIOS PARA CLIENTES HUÉRFANOS                                  ║")
    print("║                                                                                ║")
    print("║  Objetivo: Permitir que TODOS los clientes (100+) tengan usuario              ║")
    print("║  para poder generar tokens OTP de edición.                                    ║")
    print("╚════════════════════════════════════════════════════════════════════════════════╝")
    
    # Paso 1: Crear usuarios
    creados = crear_usuarios_para_clientes_huerfanos()
    
    if creados > 0:
        # Paso 2: Verificar
        total_usuarios = verificar_resultado()
        
        # Paso 3: Sincronizar
        print("\n" + "="*80)
        print("PASO 4: SINCRONIZAR TOKENS")
        print("="*80)
        print("\nEjecutando sincronización de todos los usuarios...")
        
        result = sincronizar_usuarios_desde_monitor()
        
        print(f"\n✅ Sincronización completada:")
        print(f"   • Usuarios sincronizados: {result['sincronizados']}")
        print(f"   • Errores: {result['errores']}")
        print(f"   • Total en Monitor: {result['total_monitor']}")
        
        print("\n" + "="*80)
        print("RESULTADO FINAL")
        print("="*80)
        print(f"\n🎉 ÉXITO: {result['sincronizados']} usuarios sincronizados en Tokens de Edición")
        print(f"\nTodos tus {result['total_monitor']} usuarios podrán editar ahora.")
        
        return 0
    else:
        print("\n✅ No había clientes sin usuario. Sistema ya está sincronizado.")
        return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
