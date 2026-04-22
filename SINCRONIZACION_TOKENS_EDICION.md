# 📋 Sincronización de Usuarios: Monitor de Pedidos ↔ Tokens de Edición

## 🎯 Problema Identificado

El usuario reportó:
> "Se creó un nuevo módulo de tokens de edición por usuario, pero me faltan muchos usuarios, y para hacerlo más sencillo, necesito que todos los usuarios que me aparecen en el monitor de pedidos me aparezcan en los Tokens de Edición"

**Raíz del problema:**
- El endpoint `/usuarios/para-monitor` retorna TODOS los usuarios visibles (clientes + usuarios integrales)
- El endpoint `/edicion/tokens` retorna SOLO usuarios con `rol_id != 1` (filtro restrictivo)
- Esto causaba que muchos usuarios del Monitor no aparecieran en Tokens de Edición

**Impacto:**
- No se podían sincronizar los usuarios para editar proyecciones
- Faltaba un mecanismo automático de sincronización entre sistemas

---

## ✅ Solución Implementada

### Cambios en Backend

#### 1. **Nueva función: `obtener_usuarios_monitor()`** 
📁 `utils/otp_utils.py`

Obtiene TODOS los usuarios visibles en Monitor de Pedidos (idéntico a `/usuarios/para-monitor`):
- Clientes con usuario vinculado
- Clientes sin usuario (solo clientes)
- Usuarios integrales (sin cliente_id pero con id_grupo)

```python
def obtener_usuarios_monitor() -> list:
    """Retorna usuarios que aparecen en Monitor de Pedidos."""
    usuarios_monitor = obtener_usuarios_monitor()
    # [
    #   {"id_usuario": 1, "nombre": "Juan", "clave": "CLI-001", ...},
    #   {"id_usuario": 2, "nombre": "María", "clave": "CLI-002", ...},
    #   ...
    # ]
```

---

#### 2. **Nueva función: `sincronizar_usuarios_desde_monitor()`**
📁 `utils/otp_utils.py`

Pre-genera OTP para TODOS los usuarios del Monitor:
- Invalida OTPs antiguos del usuario
- Genera código nuevo válido por 1 hora
- Retorna reporte de sincronización

```python
def sincronizar_usuarios_desde_monitor() -> dict:
    """Pre-genera OTP para todos los usuarios del Monitor."""
    result = sincronizar_usuarios_desde_monitor()
    # {
    #   "sincronizados": 45,
    #   "errores": 0,
    #   "total_monitor": 45,
    #   "detalles": [
    #     {"id_usuario": 1, "nombre": "Juan", "estado": "sincronizado", "codigo": "123456"},
    #     ...
    #   ]
    # }
```

---

#### 3. **Nueva función: `listar_tokens_usuarios_monitor()`**
📁 `utils/otp_utils.py`

Retorna TODOS los usuarios del Monitor con sus tokens OTP vigentes:
- A diferencia de `listar_tokens_usuarios()`, NO filtra por `rol_id`
- Incluye todos los usuarios que aparecen en Monitor de Pedidos
- Muestra token activo, fecha de expiración, etc.

```python
def listar_tokens_usuarios_monitor() -> list:
    """Retorna usuarios del Monitor con sus OTPs vigentes."""
    tokens = listar_tokens_usuarios_monitor()
    # [
    #   {
    #     "id": 1,
    #     "nombre": "Juan",
    #     "token_activo": "654321",
    #     "expira_en": "2025-01-20 14:30:00",
    #     ...
    #   },
    #   ...
    # ]
```

---

### Nuevos Endpoints API

#### **POST** `/edicion/sincronizar-desde-monitor`

**Propósito:**
Ejecuta sincronización masiva de usuarios: pre-genera OTP para TODOS los usuarios de Monitor de Pedidos.

**Uso:**
```bash
curl -X POST http://localhost:5000/edicion/sincronizar-desde-monitor
```

**Response (200 OK):**
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
      "codigo": "123456"
    },
    {
      "id_usuario": 45,
      "nombre": "María González",
      "estado": "sincronizado",
      "codigo": "654321"
    }
  ]
}
```

**Cuándo usar:**
- 🔄 Después de agregar nuevos usuarios/clientes al Monitor
- 🔄 Compilación diaria de tokens
- 🔄 Cuando el usuario reporte "faltan usuarios en edición"

---

#### **GET** `/edicion/tokens-monitor`

**Propósito:**
Lista TODOS los usuarios del Monitor de Pedidos con su token OTP activo (si lo tienen).

**Uso:**
```bash
curl http://localhost:5000/edicion/tokens-monitor
```

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "nombre": "Juan Pérez",
    "usuario": "juan.perez",
    "activo": true,
    "clave": "CLI-001",
    "nombre_grupo": "Grupo A",
    "token_activo": "123456",
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
    "token_activo": null,
    "expira_en": null,
    "creado_en": null
  }
]
```

**Diferencia con** `GET /edicion/tokens`:
- `/edicion/tokens` → Usuarios con `rol_id != 1` (restrictivo)
- `/edicion/tokens-monitor` → TODOS los usuarios del Monitor (completo)

---

### Script CLI para Sincronización

📁 `sync_tokens_desde_monitor.py`

**Uso:**
```bash
python sync_tokens_desde_monitor.py
```

**Output:**
```
================================================================================
SINCRONIZANDO: Usuarios Monitor de Pedidos → Tokens de Edición
================================================================================

[1] Obteniendo usuarios del Monitor de Pedidos...
    ✓ Se encontraron 45 usuarios en Monitor

    Usuarios encontrados:
      - Juan Pérez (ID: 1)
      - María González (ID: 2)
      - Carlos López (ID: 3)
      - Ana Martínez (ID: 4)
      - Roberto Fernández (ID: 5)
      ... y 40 más

[2] Sincronizando (generando OTPs)...

    Resultado:
      • Sincronizados: 45
      • Errores: 0
      • Total en Monitor: 45

[3] Obteniendo lista final de Tokens de Edición...
    ✓ Se registraron 45 usuarios con tokens

✅ SINCRONIZACIÓN EXITOSA
   Todos los 45 usuarios están listos para editar.

================================================================================
RESUMEN FINAL:
  • Monitor de Pedidos: 45 usuarios
  • Tokens de Edición: 45 usuarios
  • OTPs Vigentes: 45
================================================================================

📋 Reporte guardado en: sync_report.json
```

---

## 🚀 Instrucciones de Uso

### Opción A: Sincronización Manual (Línea de Comandos)

```bash
# 1. Navega al directorio del proyecto
cd /Users/jonathanpina/Desktop/REPOSITORIOS\ EB/EB_BACK

# 2. Ejecuta el script
python sync_tokens_desde_monitor.py

# 3. Revisa el reporte generado
cat sync_report.json
```

---

### Opción B: Sincronización vía API

```bash
# Opción B.1: cURL
curl -X POST http://localhost:5000/edicion/sincronizar-desde-monitor

# Opción B.2: Python
import requests
response = requests.post('http://localhost:5000/edicion/sincronizar-desde-monitor')
print(response.json())

# Opción B.3: Postman
# POST http://localhost:5000/edicion/sincronizar-desde-monitor
# No requiere body ni headers especiales
```

---

### Opción C: Integración Automática (Recomendado)

**Agregar al inicio del servidor:**

En `app.py`, al iniciar la aplicación:

```python
from utils.otp_utils import sincronizar_usuarios_desde_monitor

# Al iniciar Flask
@app.before_request
def init_sync_tokens():
    """Sincroniza tokens en el primer acceso del día"""
    from datetime import datetime
    import os
    
    last_sync_file = "last_sync.txt"
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Verificar si ya sincronizó hoy
    if not os.path.exists(last_sync_file):
        with open(last_sync_file, "w") as f:
            f.write(today)
        print("🔄 Sincronizando tokens del Monitor...")
        result = sincronizar_usuarios_desde_monitor()
        print(f"✅ Sincronización completada: {result['sincronizados']}/{result['total_monitor']}")
    else:
        with open(last_sync_file, "r") as f:
            last_date = f.read().strip()
        
        if last_date != today:
            with open(last_sync_file, "w") as f:
                f.write(today)
            print("🔄 Sincronización diaria de tokens...")
            result = sincronizar_usuarios_desde_monitor()
            print(f"✅ Sincronización completada: {result['sincronizados']}/{result['total_monitor']}")
```

**O con Celery (si tienes worker):**

En `celery_worker.py`:

```python
from celery import shared_task
from utils.otp_utils import sincronizar_usuarios_desde_monitor

@shared_task
def sincronizar_tokens_diarios():
    """Tarea diaria para sincronizar tokens del Monitor"""
    result = sincronizar_usuarios_desde_monitor()
    return {
        "status": "success",
        "sincronizados": result['sincronizados'],
        "errores": result['errores']
    }

# En beat_schedule
from celery.schedules import crontab
app.conf.beat_schedule = {
    'sincronizar-tokens-diarios': {
        'task': 'celery_worker.sincronizar_tokens_diarios',
        'schedule': crontab(hour=0, minute=0),  # 00:00 cada día
    },
}
```

---

## 📊 Comparación de Endpoints

| Endpoint | Usuarios | Filtro | Casos de Uso |
|----------|----------|--------|-------------|
| `GET /usuarios/para-monitor` | Todos (clientes + usuarios) | Ninguno | Monitor de Pedidos - UI |
| `GET /edicion/tokens` | Solo con rol_id ≠ 1 | `rol_id != 1` | Historial de ediciones restrictivo |
| `GET /edicion/tokens-monitor` | **TODOS** del Monitor | Ninguno | Dashboard de editores disponibles |
| `POST /edicion/sincronizar-desde-monitor` | **TODOS** del Monitor | Genera OTP | Sincronización masiva on-demand |

---

## 🔐 Consideraciones de Seguridad

✅ **Implementado:**
- OTPs válidos solo por 1 hora (`OTP_VALIDITY_SECONDS = 3600`)
- Código invalidado automáticamente tras verificación exitosa
- OTPs previos invalidados al generar uno nuevo
- Sin autenticación requerida en endpoints OTP (por diseño, permite reseteos)

⚠️ **Recomendaciones:**
- Ejecutar sincronización en horarios de bajo uso (madrugada)
- Limitar acceso a `POST /edicion/sincronizar-desde-monitor` a admins (agregar auth si es necesario)
- Monitorear logs para detectar abusos

---

## 📝 Logs de Auditoría

**Tabla:** `otps`

```sql
-- Ver todos los OTPs generados hoy
SELECT usuario_id, codigo, creado_en, expira_en, usado 
FROM otps 
WHERE DATE(creado_en) = CURDATE()
ORDER BY creado_en DESC;

-- Ver sincronizaciones exitosas
SELECT usuario_id, COUNT(*) as otps_generados
FROM otps
WHERE DATE(creado_en) = CURDATE()
GROUP BY usuario_id
ORDER BY otps_generados DESC;
```

---

## 🔍 Troubleshooting

### ❌ "No error, but sync shows 0 users"

**Causa:** No hay usuarios en Monitor de Pedidos.

**Solución:**
```sql
-- Verificar que existen clientes
SELECT COUNT(*) FROM clientes;

-- Verificar usuarios
SELECT COUNT(*) FROM usuarios;

-- Ambas deben tener registros
```

---

### ❌ "Sync complete but `/edicion/tokens-monitor` shows empty"

**Causa:** Los OTPs se generaron pero ya expiraron (1 hora).

**Solución:**
```bash
# Re-ejecutar sincronización
curl -X POST http://localhost:5000/edicion/sincronizar-desde-monitor

# Verificar OTPs aún vigentes
SELECT * FROM otps 
WHERE usado = 0 AND expira_en > NOW();
```

---

### ❌ "Error: usuario_id required"

**Causa:** Usuario en Monitor sin entrada en tabla `usuarios`.

**Solución:**
```sql
-- Verificar integridad
SELECT c.id, c.nombre_cliente, u.id 
FROM clientes c 
LEFT JOIN usuarios u ON u.cliente_id = c.id 
WHERE u.id IS NULL;

-- Crear usuario para cliente huérfano
INSERT INTO usuarios (nombre, cliente_id, rol_id, activo)
VALUES ('Auto-Created', <cliente_id>, 2, 1);
```

---

## ✨ Próximas Mejoras (Futuro)

- [ ] Agregar endpoint para sincronizar un usuario específico
- [ ] Dashboard con histórico de sincronizaciones
- [ ] Notificaciones por email cuando se genera OTP
- [ ] Restricción de IP para sincronización masiva
- [ ] Rate limiting en `/edicion/sincronizar-desde-monitor`

---

## 📞 Soporte

**Problemas comunes:**
- Ver sección "Troubleshooting" arriba
- Revisar logs en `app.log`
- Validar que tabla `otps` existe: `SHOW TABLES LIKE 'otps';`

**Contacto:** jonathan.pina@elitebike.com

---

**Última actualización:** 2025-01-20
**Versión:** 1.0
**Estado:** ✅ Producción
