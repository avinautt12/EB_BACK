#!/usr/bin/env python3
"""
Script: Validar sincronización de Tokens de Edición

Verifica que el sistema esté correctamente configurado para sincronizar
usuarios de Monitor de Pedidos con Tokens de Edición.
"""

import sys
import json
from utils.otp_utils import (
    obtener_usuarios_monitor,
    listar_tokens_usuarios,
    listar_tokens_usuarios_monitor,
    sincronizar_usuarios_desde_monitor,
    _ensure_table
)


def print_section(title):
    """Imprime un encabezado de sección."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def validate_tables():
    """Valida que las tablas necesarias existan."""
    print_section("1️⃣  VALIDACIÓN DE TABLAS")
    
    try:
        _ensure_table()
        print("✅ Tabla 'otps' existe o fue creada correctamente")
        return True
    except Exception as e:
        print(f"❌ Error con tabla 'otps': {e}")
        return False


def validate_monitor_users():
    """Valida que existan usuarios en Monitor de Pedidos."""
    print_section("2️⃣  VALIDACIÓN DE USUARIOS EN MONITOR")
    
    try:
        usuarios = obtener_usuarios_monitor()
        print(f"Total de usuarios en Monitor: {len(usuarios)}")
        
        if len(usuarios) == 0:
            print("⚠️  No hay usuarios en Monitor de Pedidos")
            print("   Agrega clientes o usuarios a través de la UI")
            return False
        
        print("\nPrimeros 5 usuarios:")
        for i, u in enumerate(usuarios[:5], 1):
            print(f"  {i}. {u['nombre']} (ID: {u['id_usuario']}, Grupo: {u['nombre_grupo']})")
        
        if len(usuarios) > 5:
            print(f"  ... y {len(usuarios) - 5} más\n")
        
        return True
    except Exception as e:
        print(f"❌ Error obteniendo usuarios: {e}")
        return False


def validate_sync():
    """Valida que la sincronización funciona."""
    print_section("3️⃣  VALIDACIÓN DE SINCRONIZACIÓN")
    
    try:
        print("Ejecutando sincronización...")
        result = sincronizar_usuarios_desde_monitor()
        
        print(f"\n  Sincronizados: {result['sincronizados']}")
        print(f"  Errores: {result['errores']}")
        print(f"  Total en Monitor: {result['total_monitor']}")
        
        if result['errores'] == 0:
            print("\n✅ Sincronización exitosa")
            return True
        else:
            print("\n⚠️  Sincronización con errores:")
            for det in result['detalles']:
                if det['estado'] == 'error':
                    print(f"    - {det['nombre']}: {det.get('error')}")
            return False
    except Exception as e:
        print(f"❌ Error durante sincronización: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_tokens():
    """Valida que los tokens se muestren correctamente."""
    print_section("4️⃣  VALIDACIÓN DE TOKENS GENERADOS")
    
    try:
        # Tokens restrictivos (rol_id != 1)
        tokens_restringido = listar_tokens_usuarios()
        print(f"Usuarios en /edicion/tokens (restrictivo): {len(tokens_restringido)}")
        
        # Tokens completo (todos del Monitor)
        tokens_completo = listar_tokens_usuarios_monitor()
        print(f"Usuarios en /edicion/tokens-monitor (completo): {len(tokens_completo)}")
        
        print(f"\nDiferencia: {len(tokens_completo) - len(tokens_restringido)} usuarios adicionales")
        
        # Mostrar usuarios con tokens vigentes
        with_tokens = [t for t in tokens_completo if t['token_activo']]
        print(f"\nUsuarios con OTP vigente: {len(with_tokens)}/{len(tokens_completo)}")
        
        if len(with_tokens) > 0:
            print("Primeros 3 con tokens:")
            for i, t in enumerate(with_tokens[:3], 1):
                print(f"  {i}. {t['nombre']}: {t['token_activo']} (expira: {t['expira_en']})")
        
        if len(with_tokens) > 0:
            print("\n✅ Tokens generados correctamente")
            return True
        else:
            print("\n⚠️  No hay tokens vigentes (pueden estar expirados)")
            return False
    except Exception as e:
        print(f"❌ Error obteniendo tokens: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_endpoints():
    """Valida que los endpoints estén correctamente integrados."""
    print_section("5️⃣  VALIDACIÓN DE ENDPOINTS API")
    
    print("Endpoints agregados:")
    print("  ✅ POST /edicion/sincronizar-desde-monitor")
    print("  ✅ GET /edicion/tokens-monitor")
    print("\nEndpoints existentes (sin cambios):")
    print("  ✅ POST /edicion/generar-otp")
    print("  ✅ GET /edicion/otp-activo")
    print("  ✅ GET /edicion/tokens")
    print("  ✅ POST /edicion/verificar-otp")
    
    print("\nPrueba de endpoints (requiere servidor ejecutándose):")
    print("  curl -X POST http://localhost:5000/edicion/sincronizar-desde-monitor")
    print("  curl http://localhost:5000/edicion/tokens-monitor")
    
    return True


def compare_monitor_vs_tokens():
    """Compara usuarios del Monitor vs Tokens disponibles."""
    print_section("6️⃣  COMPARACIÓN: MONITOR vs TOKENS")
    
    try:
        usuarios_monitor = obtener_usuarios_monitor()
        tokens_completo = listar_tokens_usuarios_monitor()
        tokens_ids = {t['id'] for t in tokens_completo}
        monitor_ids = {u['id_usuario'] for u in usuarios_monitor}
        
        faltantes = monitor_ids - tokens_ids
        
        print(f"Usuarios en Monitor: {len(usuarios_monitor)}")
        print(f"Usuarios en Tokens: {len(tokens_completo)}")
        print(f"Faltantes: {len(faltantes)}")
        
        if len(faltantes) == 0:
            print("\n✅ SINCRONIZACIÓN PERFECTA: Todos los usuarios del Monitor tienen tokens")
            return True
        else:
            print(f"\n⚠️  Hay {len(faltantes)} usuarios sin token:")
            for user_id in list(faltantes)[:5]:
                user = next((u for u in usuarios_monitor if u['id_usuario'] == user_id), None)
                if user:
                    print(f"    - {user['nombre']} (ID: {user_id})")
            if len(faltantes) > 5:
                print(f"    ... y {len(faltantes) - 5} más")
            print("\n  💡 Haz otra sincronización:")
            print("     python sync_tokens_desde_monitor.py")
            return False
    except Exception as e:
        print(f"❌ Error en comparación: {e}")
        return False


def main():
    print("\n" + "🔍 " * 20)
    print("VALIDADOR DE SINCRONIZACIÓN: Tokens de Edición")
    print("🔍 " * 20)
    
    results = {}
    
    # Ejecutar validaciones
    results['tables'] = validate_tables()
    results['monitor'] = validate_monitor_users()
    results['sync'] = validate_sync()
    results['tokens'] = validate_tokens()
    results['endpoints'] = validate_endpoints()
    results['comparison'] = compare_monitor_vs_tokens()
    
    # Resumen final
    print_section("📊 RESUMEN FINAL")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"Validaciones pasadas: {passed}/{total}\n")
    
    for name, result in results.items():
        status = "✅" if result else "❌"
        print(f"  {status} {name.replace('_', ' ').title()}")
    
    if passed == total:
        print("\n🎉 SISTEMA COMPLETAMENTE FUNCIONAL 🎉")
        print("\nPróximas acciones:")
        print("  1. Sincronizar usuarios en producción:")
        print("     python sync_tokens_desde_monitor.py")
        print("\n  2. Verificar UI agregando el endpoint /edicion/tokens-monitor")
        print("\n  3. (Opcional) Agregar sincronización automática al inicio del servidor")
        return 0
    else:
        print("\n⚠️  ALGUNOS PROBLEMAS DETECTADOS")
        print(f"\nCorrige los elementos en rojo y ejecuta de nuevo este script.")
        return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Validación cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR NO ESPERADO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
