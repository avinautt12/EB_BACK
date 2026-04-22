#!/usr/bin/env python3
"""
Script: Sincronizar usuarios de Monitor de Pedidos con Tokens de Edición

Propósito:
    Pre-genera tokens OTP para TODOS los usuarios que aparecen en el Monitor de Pedidos.
    Esto asegura que todos puedan usar el sistema de edición sin necesidad de generar
    tokens on-demand.

Uso:
    python sync_tokens_desde_monitor.py
    
    O automático vía endpoint:
    curl -X POST http://localhost:5000/edicion/sincronizar-desde-monitor

Resultado:
    - Invalida cualquier OTP anterior del usuario
    - Genera un nuevo código OTP válido por 1 hora
    - Retorna reporte de sincronización (sincronizados, errores, detalles)
"""

import sys
import json
from utils.otp_utils import (
    obtener_usuarios_monitor,
    sincronizar_usuarios_desde_monitor,
    listar_tokens_usuarios_monitor
)


def main():
    print("=" * 80)
    print("SINCRONIZANDO: Usuarios Monitor de Pedidos → Tokens de Edición")
    print("=" * 80)
    
    # Paso 1: Obtener usuarios del monitor
    print("\n[1] Obteniendo usuarios del Monitor de Pedidos...")
    usuarios_monitor = obtener_usuarios_monitor()
    print(f"    ✓ Se encontraron {len(usuarios_monitor)} usuarios en Monitor")
    
    if len(usuarios_monitor) > 0:
        print("\n    Usuarios encontrados:")
        for u in usuarios_monitor[:5]:  # Mostrar los primeros 5
            print(f"      - {u['nombre']} (ID: {u['id_usuario']})")
        if len(usuarios_monitor) > 5:
            print(f"      ... y {len(usuarios_monitor) - 5} más")
    
    # Paso 2: Sincronizar
    print("\n[2] Sincronizando (generando OTPs)...")
    result = sincronizar_usuarios_desde_monitor()
    
    print(f"\n    Resultado:")
    print(f"      • Sincronizados: {result['sincronizados']}")
    print(f"      • Errores: {result['errores']}")
    print(f"      • Total en Monitor: {result['total_monitor']}")
    
    # Paso 3: Listar tokens de edición
    print("\n[3] Obteniendo lista final de Tokens de Edición...")
    tokens_finales = listar_tokens_usuarios_monitor()
    print(f"    ✓ Se registraron {len(tokens_finales)} usuarios con tokens")
    
    # Paso 4: Validación
    if result['sincronizados'] == result['total_monitor']:
        print("\n✅ SINCRONIZACIÓN EXITOSA")
        print(f"   Todos los {result['total_monitor']} usuarios están listos para editar.")
    else:
        print("\n⚠️  SINCRONIZACIÓN CON ERRORES")
        print(f"   Se sincronizaron {result['sincronizados']} de {result['total_monitor']}")
        if result['errores'] > 0:
            print(f"   {result['errores']} usuarios tuvieron problemas:")
            for det in result['detalles']:
                if det['estado'] == 'error':
                    print(f"      - {det['nombre']}: {det.get('error', 'Error desconocido')}")
    
    # Resumen final
    print("\n" + "=" * 80)
    print("RESUMEN FINAL:")
    print(f"  • Monitor de Pedidos: {len(usuarios_monitor)} usuarios")
    print(f"  • Tokens de Edición: {len(tokens_finales)} usuarios")
    print(f"  • OTPs Vigentes: {sum(1 for t in tokens_finales if t['token_activo'])}")
    print("=" * 80)
    
    # Guardar reporte
    reporte = {
        "usuarios_monitor": len(usuarios_monitor),
        "tokens_edicion": len(tokens_finales),
        "result_sync": result
    }
    
    with open("sync_report.json", "w") as f:
        json.dump(reporte, f, indent=2, default=str)
    print(f"\n📋 Reporte guardado en: sync_report.json")
    
    return 0 if result['errores'] == 0 else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
