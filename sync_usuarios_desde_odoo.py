#!/usr/bin/env python3
"""
═════════════════════════════════════════════════════════════════════════════════
SINCRONIZACIÓN: res.partner (Odoo) → usuarios (BD Local)
═════════════════════════════════════════════════════════════════════════════════

Este script sincroniza TODOS los partners activos de Odoo a la tabla usuarios
en tu BD local. Esto es lo que necesitas para que los 100 usuarios del servidor
aparezcan en tu Tokens de Edición local.

PROCESO:
1. Conecta a Odoo
2. Obtiene TODOS los partners (res.partner) activos y confiables
3. Para cada partner:
   - Si YA existe en usuarios (por cliente_id): DESCARTAR
   - Si NO existe: CREAR nuevo usuario vinculado al cliente
4. Resultado: Sincronizados todos los 100 usuarios

USAGE:
    python3 sync_usuarios_desde_odoo.py [--dry-run]

OPTIONS:
    --dry-run   : Muestra qué se haría sin hacer cambios
"""

import sys
import argparse
from datetime import datetime
from utils.odoo_utils import get_odoo_models, ODOO_DB, ODOO_PASSWORD
from db_conexion import obtener_conexion
import re

# ═══════════════════════════════════════════════════════════════════════════════
# 1. OBTENER PARTNERS DESDE ODOO
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_partners_desde_odoo(uid, models):
    """Obtiene todos los partners activos y confiables desde Odoo."""
    print("🔄 Buscando partners en Odoo...")
    
    try:
        partners = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'res.partner', 'search_read',
            [[
                ['active', '=', True],
                ['customer_rank', '>', 0],  # Solo clientes
            ]],
            {
                'fields': [
                    'id', 'name', 'ref', 'email', 'phone',
                    'customer_rank', 'supplier_rank', 'active'
                ],
                'limit': 0  # Sin límite
            }
        )
        
        print(f"✅ Encontrados {len(partners)} partners activos en Odoo")
        return partners
        
    except Exception as e:
        print(f"❌ Error obteniendo partners de Odoo: {e}")
        return []

# ═══════════════════════════════════════════════════════════════════════════════
# 2. OBTENER CLIENTES LOCALES
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_clientes_locales(conexion):
    """Obtiene map de clientes locales por clave/ref Odoo."""
    print("🔄 Cargando clientes de BD local...")
    
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, clave, nombre_cliente, id_grupo
        FROM clientes
        WHERE clave IS NOT NULL
        ORDER BY clave
    """)
    
    clientes = cursor.fetchall()
    cursor.close()
    
    # Map por clave (ref en Odoo)
    mapa_clave = {}
    for c in clientes:
        if c['clave']:
            mapa_clave[c['clave'].strip().upper()] = c
    
    print(f"✅ Cargados {len(clientes)} clientes locales (map por clave: {len(mapa_clave)})")
    return clientes, mapa_clave

# ═══════════════════════════════════════════════════════════════════════════════
# 3. OBTENER USUARIOS EXISTENTES
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_usuarios_existentes(conexion):
    """Obtiene mapa de usuarios ya en BD local."""
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, cliente_id, usuario
        FROM usuarios
        WHERE cliente_id IS NOT NULL
    """)
    
    usuarios = cursor.fetchall()
    cursor.close()
    
    # Map por cliente_id
    mapa_usuarios = {}
    for u in usuarios:
        if u['cliente_id']:
            mapa_usuarios[u['cliente_id']] = u
    
    print(f"✅ Cargados {len(usuarios)} usuarios locales vinculados a clientes")
    return usuarios, mapa_usuarios

# ═══════════════════════════════════════════════════════════════════════════════
# 4. SINCRONIZAR
# ═════════════════════════════════════════════════════════════════════════════

def sincronizar_usuarios(uid, models, conexion, dry_run=False):
    """Sincroniza partners de Odoo a usuarios locales."""
    
    # Obtener datos
    partners_odoo = obtener_partners_desde_odoo(uid, models)
    clientes_locales, mapa_clave = obtener_clientes_locales(conexion)
    usuarios_locales, mapa_usuarios = obtener_usuarios_existentes(conexion)
    
    if not partners_odoo:
        print("❌ No hay partners en Odoo para sincronizar")
        return 0, 0, 0
    
    print(f"\n📊 ANÁLISIS:")
    print(f"  • Partners en Odoo: {len(partners_odoo)}")
    print(f"  • Clientes en BD local: {len(clientes_locales)}")
    print(f"  • Usuarios vinculados existentes: {len(usuarios_locales)}")
    
    # Procesamiento
    sincronizados = 0
    ya_existen = 0
    sin_cliente_local = 0
    errores = 0
    
    cursor = conexion.cursor()
    
    for partner in partners_odoo:
        partner_id = partner['id']
        partner_name = partner['name']
        
        # Manejar refs que pueden ser booleanas o strings
        partner_ref = partner.get('ref')
        if isinstance(partner_ref, str):
            partner_ref = partner_ref.strip().upper() or None
        else:
            partner_ref = None
        
        # Manejar email y phone
        partner_email = partner.get('email')
        if isinstance(partner_email, str):
            partner_email = partner_email.strip() or None
        else:
            partner_email = None
            
        partner_phone = partner.get('phone')
        if isinstance(partner_phone, str):
            partner_phone = partner_phone.strip() or None
        else:
            partner_phone = None
        
        # Buscar cliente local por ref
        cliente_local = mapa_clave.get(partner_ref) if partner_ref else None
        
        if not cliente_local:
            # Intenta buscar por nombre (fallback)
            for c in clientes_locales:
                if c['nombre_cliente'].upper() == partner_name.upper():
                    cliente_local = c
                    break
        
        if not cliente_local:
            sin_cliente_local += 1
            print(f"⚠️  Partner '{partner_name}' (ref={partner_ref}) NO tiene cliente local")
            continue
        
        cliente_id = cliente_local['id']
        
        # Verificar si ya existe usuario para este cliente
        if cliente_id in mapa_usuarios:
            ya_existen += 1
            print(f"✓ Usuario ya existe para cliente '{cliente_local['nombre_cliente']}'")
            continue
        
        # CREAR nuevo usuario
        try:
            # Generar username único
            username = _generar_username(partner_name, cursor, conexion)
            
            # Datos del usuario
            nombre_usuario = partner_name + (f" ({partner_ref})" if partner_ref else "")
            contrasena_temp = _generar_contrasena_temporal()
            
            if dry_run:
                print(f"[DRY RUN] Crear usuario:")
                print(f"  - Cliente: {cliente_local['nombre_cliente']} (ID={cliente_id})")
                print(f"  - Usuario: {username}")
                print(f"  - Nombre: {nombre_usuario}")
                print(f"  - Grupo: {cliente_local.get('id_grupo', 'N/A')}")
                sincronizados += 1
            else:
                # INSERT
                cursor.execute("""
                    INSERT INTO usuarios (
                        nombre, correo, usuario, contrasena,
                        cliente_id, id_grupo, rol_id, activo, clave
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    nombre_usuario,
                    partner_email or f"{username}@elitebike.local",
                    username,
                    contrasena_temp,
                    cliente_id,
                    cliente_local.get('id_grupo'),
                    2,  # rol_id = 2 (Usuario normal)
                    1,  # activo = 1
                    partner_ref
                ))
                
                print(f"✅ CREADO usuario '{username}' para cliente '{cliente_local['nombre_cliente']}'")
                sincronizados += 1
                
        except Exception as e:
            print(f"❌ Error al crear usuario para '{cliente_local['nombre_cliente']}': {e}")
            errores += 1
    
    cursor.close()
    
    # Commit
    if not dry_run and (sincronizados > 0 or errores == 0):
        conexion.commit()
        print(f"\n✅ Cambios guardados en BD local")
    elif dry_run:
        conexion.rollback()
    
    return sincronizados, ya_existen, sin_cliente_local

# ═══════════════════════════════════════════════════════════════════════════════
# 5. UTILIDADES
# ═════════════════════════════════════════════════════════════════════════════════

def _generar_username(nombre, cursor, conexion):
    """Genera un username único basado en el nombre."""
    # Usar primeras letras + random para garantizar unicidad
    import random
    import string
    
    partes = nombre.upper().split()
    base = ''.join([p[0] for p in partes if p])[:4]
    
    # Asegurar unicidad
    for i in range(1000):
        suffix = ''.join(random.choices(string.digits, k=3))
        username_candidato = f"{base}{suffix}"
        
        cursor.execute("SELECT id FROM usuarios WHERE usuario = %s", (username_candidato,))
        if not cursor.fetchone():
            return username_candidato
    
    raise RuntimeError(f"No se pudo generar username único para '{nombre}'")

def _generar_contrasena_temporal():
    """Genera contraseña temporal segura."""
    import random
    import string
    
    chars = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(random.choice(chars) for _ in range(12))

# ═════════════════════════════════════════════════════════════════════════════════
# 6. MAIN
# ═════════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Simular sin hacer cambios')
    args = parser.parse_args()
    
    print("=" * 85)
    print("SINCRONIZACIÓN: Odoo res.partner → BD Local usuarios")
    print("=" * 85)
    
    if args.dry_run:
        print("⚠️  MODO DRY-RUN: No se harán cambios\n")
    
    try:
        # 1. Conectar a Odoo
        print("🔐 Conectando a Odoo...")
        uid, models, odoo_err = get_odoo_models()
        
        if not uid or not models:
            print(f"❌ No se pudo autenticar en Odoo: {odoo_err}")
            return 1
        
        print(f"✅ Conectado a Odoo (UID={uid})\n")
        
        # 2. Conectar BD local
        print("🔐 Conectando a BD local...")
        conexion = obtener_conexion()
        print(f"✅ Conectado a BD local\n")
        
        # 3. Sincronizar
        sincronizados, ya_existen, sin_cliente = sincronizar_usuarios(uid, models, conexion, args.dry_run)
        
        # 4. Resumen
        print("\n" + "=" * 85)
        print("📊 RESUMEN:")
        print(f"  • Usuarios creados: {sincronizados}")
        print(f"  • Usuarios ya existentes: {ya_existen}")
        print(f"  • Partners sin cliente local: {sin_cliente}")
        print("=" * 85)
        
        conexion.close()
        
        if args.dry_run:
            print("\n✅ DRY-RUN completado sin hacer cambios")
        else:
            print("\n✅ SINCRONIZACIÓN COMPLETADA")
            print("\n💡 Próximo paso:")
            print("   python3 diagnostico_usuarios.py")
            print("   # Debe mostrar ahora: ~100 usuarios capturables")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
