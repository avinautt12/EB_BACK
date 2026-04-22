# Referencia — Backend (Flask + Celery + MySQL)

## Tabla de contenidos

1. Plantilla de blueprint completo
2. Patrón MySQL (try/finally + rollback)
3. Tarea Celery
4. Registro en `app.py`
5. Configuración y variables de entorno
6. Logging
7. Checklist antes de cerrar un PR

## 1. Plantilla de blueprint completo

```python
# EB_BACK/routes/<dominio>.py
from flask import Blueprint, request, jsonify
import logging

from db_conexion import obtener_conexion
from utils.jwt_utils import verificar_token
from utils.odoo_utils import (
    get_odoo_models, ODOO_DB, ODOO_PASSWORD, ODOO_COMPANY_ID,
)

logger = logging.getLogger(__name__)

<dominio>_bp = Blueprint('<dominio>', __name__, url_prefix='')


def _auth_usuario():
    """Valida el JWT del header y devuelve el payload, o (None, response) si falla."""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None, (jsonify({"error": "Token no proporcionado"}), 401)
    token = auth.split(' ', 1)[1]
    payload = verificar_token(token)
    if not payload:
        return None, (jsonify({"error": "Token inválido o expirado"}), 401)
    return payload, None


@<dominio>_bp.route('/<dominio>', methods=['GET'])
def listar_<dominio>():
    payload, err = _auth_usuario()
    if err:
        return err

    conexion, cursor = None, None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT id, nombre FROM <tabla> WHERE activo = 1")
        registros = cursor.fetchall()
        return jsonify({"datos": registros}), 200

    except Exception as e:
        logger.exception("Error listando <dominio>: %s", e)
        return jsonify({"error": "Error interno"}), 500

    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()


@<dominio>_bp.route('/<dominio>', methods=['POST'])
def crear_<dominio>():
    payload, err = _auth_usuario()
    if err:
        return err

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Payload JSON requerido"}), 400

    nombre = (data.get('nombre') or '').strip()
    if not nombre:
        return jsonify({"error": "El campo 'nombre' es obligatorio"}), 400

    conexion, cursor = None, None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            "INSERT INTO <tabla> (nombre, creado_por) VALUES (%s, %s)",
            (nombre, payload.get('usuario')),
        )
        conexion.commit()
        nuevo_id = cursor.lastrowid
        return jsonify({"id": nuevo_id}), 201

    except Exception as e:
        if conexion:
            try:
                conexion.rollback()
            except Exception:
                pass
        logger.exception("Error creando <dominio>: %s", e)
        return jsonify({"error": "Error interno"}), 500

    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()
```

## 2. Patrón MySQL (try/finally + rollback)

Siempre usa `cursor(dictionary=True)` para que los resultados vengan como dict (más fácil de serializar a JSON). El orden en `finally` es: cursor primero, conexión después.

```python
conexion, cursor = None, None
try:
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT ...", (param1, param2))
    filas = cursor.fetchall()
    # lógica
    conexion.commit()  # solo si hubo INSERT/UPDATE/DELETE
except Exception as e:
    if conexion:
        try:
            conexion.rollback()
        except Exception:
            pass
    logger.exception("...")
    raise
finally:
    if cursor:
        cursor.close()
    if conexion:
        conexion.close()
```

**Importante:** nunca concatenes valores al SQL. Siempre usa `%s` con tupla de parámetros.

## 3. Tarea Celery

Cuando una operación toma más de ~2 segundos, va a Celery. El worker ya está configurado en `celery_worker.py`.

```python
# EB_BACK/celery_worker.py (agregar la tarea)
from celery_worker import celery_app

@celery_app.task(bind=True, name='tasks.sincronizar_pedidos_odoo')
def sincronizar_pedidos_odoo(self, desde_fecha):
    """Trae pedidos de Odoo desde una fecha y los inserta en MySQL."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        # ... lógica pesada
        logger.info("Sincronización completada")
        return {"status": "ok", "sincronizados": total}
    except Exception as e:
        logger.exception("Sincronización falló")
        # Celery reintenta si usas self.retry(...)
        raise self.retry(exc=e, countdown=60, max_retries=3)
```

Dispararla desde una ruta:

```python
from celery_worker import sincronizar_pedidos_odoo

task = sincronizar_pedidos_odoo.delay('2025-01-01')
return jsonify({"task_id": task.id}), 202
```

Consultar estado:

```python
from celery.result import AsyncResult
from celery_worker import celery_app

@<dominio>_bp.route('/tareas/<task_id>', methods=['GET'])
def estado_tarea(task_id):
    res = AsyncResult(task_id, app=celery_app)
    return jsonify({
        "task_id": task_id,
        "state": res.state,
        "result": res.result if res.ready() else None,
    }), 200
```

Ver `CELERY_ASYNC_ARCHITECTURE.md` en la raíz para arquitectura completa.

## 4. Registro en `app.py`

El blueprint NO está vivo hasta que se registra. En `create_app()`:

```python
from routes.<dominio> import <dominio>_bp
# ...
app.register_blueprint(<dominio>_bp)
```

Si el endpoint devuelve 404 después de implementarlo, lo más probable es que olvidaste este paso.

## 5. Configuración y variables de entorno

Variables que deben existir en `.env`:

```
ODOO_ENV=prod            # o 'test'
ODOO_PROD_URL=https://ebik.odoo.com
ODOO_PROD_DB=ebik-prod-15375115
ODOO_PROD_USER=sistemas@elitebike-mx.com
ODOO_PROD_PASSWORD=***
ODOO_TEST_URL=...
ODOO_TEST_DB=...
ODOO_TEST_USER=...
ODOO_TEST_PASSWORD=...
JWT_SECRET=***
DB_HOST=...
DB_USER=...
DB_PASSWORD=***
DB_NAME=...
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

## 6. Logging

```python
import logging
logger = logging.getLogger(__name__)

logger.debug("Traza detallada solo en desarrollo")
logger.info("Usuario %s inició sesión", usuario)
logger.warning("Intento de login fallido para %s", usuario)
logger.error("Error procesando pago %s", pago_id, exc_info=True)
logger.exception("Resumen del error (incluye stack automáticamente)")
```

Reglas:
- Nunca loggees passwords, tokens JWT completos ni el cuerpo completo de una respuesta que contenga PII.
- Usa `%s` placeholders (lazy formatting); no hagas `logger.info(f"...")` — esto formatea aunque el nivel esté deshabilitado.
- `exception()` incluye el stack automáticamente, no hace falta `exc_info=True`.

## 7. Checklist antes de cerrar un cambio

- [ ] Blueprint registrado en `app.py`
- [ ] Todas las rutas no-públicas validan JWT
- [ ] Queries Odoo filtran por `ODOO_COMPANY_ID` cuando aplica
- [ ] Queries MySQL usan placeholders `%s` (no f-strings)
- [ ] try/finally cierra cursor y conexión
- [ ] `rollback()` en caminos de error
- [ ] `logger.exception` en cada except
- [ ] Mensajes de error al cliente en español y sin detalles internos
- [ ] Tests en `tests/test_<dominio>.py` pasan (`pytest tests/ -q`)
- [ ] Sin `print()` nuevos en código de producción
- [ ] Sin credenciales hardcodeadas
