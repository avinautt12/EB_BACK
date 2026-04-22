# 🚀 Referencia Rápida: Sincronización Tokens

## 🎯 La Misión
Sincronizar TODOS los usuarios del Monitor de Pedidos con el módulo de Tokens de Edición.

## ⚡ Quick Start

```bash
# 1. Sincronizar
python3 sync_tokens_desde_monitor.py

# 2. Validar
python3 validate_tokens_sync.py

# 3. Ver resultados
curl http://localhost:5000/edicion/tokens-monitor
```

---

## 📡 API Reference

### POST /edicion/sincronizar-desde-monitor
Pre-genera OTP para TODOS los usuarios del Monitor.

**Request:**
```bash
curl -X POST http://localhost:5000/edicion/sincronizar-desde-monitor
```

**Response:**
```json
{
  "sincronizados": 45,
  "errores": 0,
  "total_monitor": 45,
  "detalles": [
    {
      "id_usuario": 1,
      "nombre": "Juan Pérez",
      "estado": "sincronizado",
      "codigo": "654321"
    },
    {
      "id_usuario": 2,
      "nombre": "María González",
      "estado": "sincronizado",
      "codigo": "123456"
    }
  ]
}
```

---

### GET /edicion/tokens-monitor
Retorna TODOS los usuarios del Monitor con su OTP vigente.

**Request:**
```bash
curl http://localhost:5000/edicion/tokens-monitor
```

**Response:**
```json
[
  {
    "id": 1,
    "nombre": "Juan Pérez",
    "usuario": "juan.perez",
    "activo": true,
    "clave": "CLI-001",
    "nombre_grupo": "Grupo A",
    "token_activo": "654321",
    "expira_en": "2025-01-20 14:30:00",
    "creado_en": "2025-01-20 13:30:00"
  },
  {
    "id": 2,
    "nombre": "María González",
    "usuario": "maria.gonzalez",
    "activo": true,
    "clave": "CLI-002",
    "nombre_grupo": "Grupo B",
    "token_activo": "123456",
    "expira_en": "2025-01-20 14:45:00",
    "creado_en": "2025-01-20 13:45:00"
  },
  {
    "id": 3,
    "nombre": "Carlos López",
    "usuario": null,
    "activo": false,
    "clave": "CLI-003",
    "nombre_grupo": "Grupo C",
    "token_activo": null,
    "expira_en": null,
    "creado_en": null
  }
]
```

---

## 🔄 Flujo Visual

```
MONITOR DE PEDIDOS                TOKENS DE EDICIÓN
┌──────────────────┐              ┌─────────────────┐
│ Juan (CLI-001)   │ ──────────→  │ Juan: 654321    │
│ María (CLI-002)  │              │ María: 123456   │
│ Carlos (CLI-003) │              │ Carlos: pending │
└──────────────────┘              └─────────────────┘
       ↑                                   ↑
       │                                   │
 /usuarios/para-monitor            /edicion/tokens-monitor
```

---

## 🔐 Ficha Técnica

| Aspecto | Valor |
|--------|-------|
| **OTP Validity** | 3600 segundos (1 hora) |
| **Código Format** | 6 dígitos (000000-999999) |
| **Tabla** | `otps` |
| **Campos** | usuario_id, codigo, expira_en, usado |
| **Índices** | idx_usuario, idx_codigo, idx_activo |

---

## 📊 Estadísticas Esperadas

**Con 45 usuarios en Monitor:**
```
✅ Sincronización:
   - Tiempo: ~2-5 segundos
   - OTPs generados: 45
   - Errores: 0

✅ Endpoints:
   - /edicion/tokens-monitor: 45 usuarios
   - OTPs vigentes: 45
```

---

## 🆘 Errores Comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `usuario_id not found` | Usuario en Monitor sin entrada en BD | Crear usuario para cliente |
| `OTP expirado` | OTP >1 hora | Volver a sincronizar |
| `0 usuarios sincronizados` | Monitor vacío | Agregar clientes/usuarios |
| `Conexión rechazada` | Servidor desactivado | Iniciar servidor Flask |

---

## 🧪 Tests

```bash
# Ejecutar todos
python3 test_sync_tokens.py

# Resultado esperado:
# ✓ test_obtener_usuarios_monitor_retorna_lista
# ✓ test_usuarios_monitor_tienen_campos_requeridos
# ✓ test_generar_otp_retorna_codigo_valido
# ✓ test_verificar_otp_funcionamiento
# ✓ test_sincronizar_usuarios_retorna_estructura_esperada
# ✓ test_listar_tokens_usuarios_monitor
# ✓ test_comparacion_endpoints
# ✓ test_sincronizacion_masiva
```

---

## 📝 Logs SQL

```sql
-- Ver OTPs recientes
SELECT usuario_id, codigo, expira_en, usado 
FROM otps 
ORDER BY creado_en DESC 
LIMIT 10;

-- Ver usuarios sin OTP
SELECT u.id, u.nombre 
FROM usuarios u 
LEFT JOIN otps o ON u.id = o.usuario_id 
WHERE o.id IS NULL 
AND u.rol_id != 1;

-- Limpiar OTPs expirados
DELETE FROM otps 
WHERE expira_en < NOW() 
OR usado = 1;
```

---

## 🔧 Integración Recomendada

**Para sincronización automática diaria:**

```python
# En app.py
from celery import Celery
from utils.otp_utils import sincronizar_usuarios_desde_monitor

@celery.task
def sincronizar_tokens_diarios():
    result = sincronizar_usuarios_desde_monitor()
    return {
        "status": "success",
        "sincronizados": result['sincronizados']
    }

# Ejecutar: celery -A app beat
```

Ver [INTEGRACION_TOKENS_SYNC.md](INTEGRACION_TOKENS_SYNC.md) para opciones completas.

---

## ✅ Checklist de Implementación

- [ ] Validar sistema: `python3 validate_tokens_sync.py`
- [ ] Sincronizar usuarios: `python3 sync_tokens_desde_monitor.py`
- [ ] Probar endpoints:
  - [ ] `POST /edicion/sincronizar-desde-monitor`
  - [ ] `GET /edicion/tokens-monitor`
- [ ] Ejecutar tests: `python3 test_sync_tokens.py`
- [ ] (Opcional) Agregar integración automática
- [ ] Documentar en guía de uso del cliente

---

## 📚 Documentación Relacionada

- [SINCRONIZACION_TOKENS_EDICION.md](SINCRONIZACION_TOKENS_EDICION.md) - Guía completa
- [INTEGRACION_TOKENS_SYNC.md](INTEGRACION_TOKENS_SYNC.md) - Opciones de integración
- [sync_tokens_desde_monitor.py](sync_tokens_desde_monitor.py) - Script CLI
- [validate_tokens_sync.py](validate_tokens_sync.py) - Validador
- [test_sync_tokens.py](test_sync_tokens.py) - Tests

---

## 🎯 Resultado

**Antes:**
- ❌ Usuarios faltante en Tokens
- ❌ Sin sincronización automática
- ❌ Proceso manual tedioso

**Después:**
- ✅ TODOS los usuarios del Monitor → Tokens
- ✅ Sincronización on-demand
- ✅ Un comando, listo

---

**Estado**: ✅ Completado  
**Versión**: 1.0  
**Última actualización**: 2025-01-20
