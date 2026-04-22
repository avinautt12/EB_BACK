---
name: eb-stack
description: Convenciones, patrones y guardarraíles del proyecto Elite Bike (EB_BACK + EB_FRONT). Úsala SIEMPRE que el usuario pida crear, modificar, depurar o revisar código relacionado con este proyecto: endpoints Flask, blueprints, integración XML-RPC con Odoo (res.partner, sale.order, stock.picking, account.payment, etc.), tareas Celery, consultas MySQL, services de Angular 19, components, interceptors, guards, o cuando mencione archivos de EB_BACK o EB_FRONT. También aplícala cuando el usuario diga "agregar endpoint", "nueva ruta", "service de Angular", "conectar a Odoo", "tarea en background", "dashboard", "importar facturas", o cualquier tarea del stack Elite Bike aunque no nombre explícitamente la skill. Evita proponer librerías o patrones alternos a los ya establecidos sin justificación explícita.
---

# Skill — Elite Bike Stack

Esta skill contiene las convenciones del proyecto Elite Bike. Respetarlas ahorra tiempo, previene bugs en producción y mantiene consistente el código entre ramas, devs y sesiones de Claude.

## Cuándo activarla

Actívala cuando se cumpla cualquiera de estos disparadores, aunque el usuario no la invoque por nombre:

- El usuario menciona rutas dentro de `EB_BACK/` o `EB_FRONT/`.
- Habla de Odoo, XML-RPC, `res.partner`, `sale.order`, `stock.picking`, `account.move`, `account.payment`, `stock.move`, o modelos de Odoo en general.
- Pide agregar/modificar un endpoint Flask, un Blueprint, un modelo MySQL, una tarea Celery, un service de Angular, un component, un guard, un interceptor, un pipe o una directiva.
- Menciona "monitor Odoo", "facturas", "pedidos", "clientes", "metas", "flujo", "multimarcas", "retroactivos", "caratulas", "proyecciones" u otros dominios listados en `EB_BACK/routes/`.
- Solicita crear tests, depurar errores, revisar seguridad o mejorar performance en este proyecto.

Si la tarea involucra claramente otro proyecto ajeno a Elite Bike, no uses esta skill.

## Mapa del proyecto

```
EB_BACK/                        Flask 3 + Celery + Redis + MySQL + Odoo XML-RPC
├── app.py                      Factory create_app(), CORS dinámico, registro de blueprints
├── celery_worker.py            Celery app + tasks asíncronas
├── db_conexion.py              obtener_conexion() MySQL
├── requirements.txt
├── .env                        Secretos (ODOO_*, JWT_SECRET, DB_*) — NUNCA commitear
├── routes/                     Blueprints por dominio (auth, clientes, metas, monitor_odoo, ...)
├── models/                     Queries MySQL crudas por dominio
├── services/                   Lógica de negocio reutilizable
├── utils/
│   ├── odoo_utils.py           get_odoo_models() con retries + ODOO_COMPANY_ID
│   ├── cache_manager.py        Caché por TTL
│   ├── jwt_utils.py            generar_token(), verificar_token()
│   ├── seguridad.py            hash_password(), verificar_password() (bcrypt)
│   ├── email_utils.py          Envío SMTP
│   └── estados_pedidos.py      Normalización de estados Odoo
└── tests/                      pytest

EB_FRONT/                       Angular 19 standalone + Material + Socket.io-client
├── angular.json
├── proxy.conf.json             /api → http://127.0.0.1:5000 (rewrite ^/api → '')
├── src/
│   ├── environments/           environment.ts / environment.prod.ts con apiUrl
│   └── app/
│       ├── services/           Uno por dominio, con .spec.ts obligatorio
│       ├── components/         UI reutilizable
│       ├── views/              Pantallas/rutas
│       ├── guards/             Control de acceso
│       ├── interceptors/       JWT, errores, headers
│       ├── pipes/              Transformaciones de vista
│       └── directives/
```

## Reglas no negociables

Estas son las reglas que NUNCA se deben violar sin que el usuario lo pida explícitamente y con razón. Si detectas una tentación de saltártelas, detente y pide confirmación.

### 1. Seguridad y entorno

- Las credenciales viven SOLO en `.env`. Nunca hardcodees `ODOO_PASSWORD`, `JWT_SECRET`, passwords de MySQL ni tokens en código, comentarios, logs ni mensajes de error expuestos al cliente.
- Al leer configuración de Odoo, usa siempre `from utils.odoo_utils import get_odoo_models, ODOO_DB, ODOO_PASSWORD, ODOO_COMPANY_ID`. No vuelvas a leer `os.getenv('ODOO_PASSWORD')` por tu cuenta.
- **Blindaje multi-empresa**: TODA consulta Odoo sobre modelos con `company_id` (casi todos los financieros/operativos: `account.move`, `account.payment`, `sale.order`, `stock.picking`, `purchase.order`, etc.) debe filtrar por `('company_id', '=', ODOO_COMPANY_ID)` como primer criterio del domain. Omitirlo mezcla datos de otras empresas y rompe reportes silenciosamente.
- Todo endpoint que no sea público (registro, login, healthcheck) debe validar el JWT con `utils.jwt_utils`. Si falta, agrégalo.
- CORS: agrega orígenes nuevos en la lista `allowed_origins` de `app.py`. No uses `*` nunca.
- Valida el `Content-Type` en endpoints que reciben JSON; rechaza con 400 si falta o es inválido.

### 2. Logging y manejo de errores

Esto importa porque los bugs en Odoo se manifiestan como respuestas vacías o incompletas en lugar de excepciones.

- En backend usa `logging` (no `print` en código productivo; los `print` de `odoo_utils.py` son legacy). Importa con `import logging` y loggea al nivel correcto: `DEBUG` para trazas detalladas, `INFO` para eventos normales, `WARNING` para situaciones recuperables, `ERROR` con `exc_info=True` para excepciones.
- Todo `execute_kw` contra Odoo va envuelto en `try/except Exception as e`. Dentro del except: `logging.exception("Odoo <modelo>.<método> falló: %s", e)` y devuelve un fallback seguro (lista vacía, 0.0, None) o re-lanza según el caso. Nunca dejes que un fallo de Odoo tumbe el endpoint completo sin log.
- Conexiones MySQL: patrón obligatorio con `try/finally` que cierra `cursor` y `conexion`, y `conexion.rollback()` en caso de excepción antes de re-lanzar. El patrón canónico está en `routes/auth.py` y `routes/monitor_odoo.py`.
- En frontend, `HttpClient` devuelve observables que fallan con `HttpErrorResponse`. Usa `catchError` en el service o deja que el interceptor global lo maneje — no dupliques lógica de manejo en cada component.

### 3. Tests

No se considera completada una tarea de código hasta que tenga tests, salvo que el usuario diga explícitamente "sin tests".

- **Backend**: cada endpoint nuevo o modificado debe tener un archivo `tests/test_<dominio>.py` con pytest + `pytest-mock`. Mockea `utils.odoo_utils.get_odoo_models` para no golpear la instancia real durante las pruebas.
- **Frontend**: cada service nuevo debe tener su `<nombre>.service.spec.ts` con Jasmine + `HttpClientTestingModule`. Cada component con lógica no trivial debe tener `.spec.ts`.
- Antes de cerrar un cambio, corre `pytest tests/ -q` en backend y `ng test --watch=false` en frontend. Reporta si fallan.

### 4. Performance

- **Caché**: si un endpoint consulta datos que cambian cada minuto o menos, usa `utils/cache_manager.py` con TTL apropiado. En frontend, replica el patrón `BehaviorSubject + tap + shareReplay` ya usado en `monitor-odoo.service.ts`.
- **Celery**: cualquier tarea que tome más de ~2 segundos (importar Excel, recalcular totales, sincronizar Odoo masivo, enviar lotes de correos) va a Celery, no al request. Registra la tarea en `celery_worker.py` y devuelve el `task_id` al cliente para polling.
- **Odoo — evita N+1**: cuando leas órdenes con líneas, NO hagas un `search_read` por cada `order_line`. Acumula todos los IDs y haz UN `search_read` final sobre `sale.order.line` con `[('id','in', ids)]`. El patrón está en `tmp_odo_test.py`.
- **Paginación**: para listados grandes (>500 registros) usa `limit` y `offset` en `search_read`, o filtra por fecha.
- **Introspección defensiva**: si un campo de Odoo podría no existir (varía entre versiones: `quantity_done` vs `qty_done`), valida con `fields_get` antes de pedirlo. Ejemplo en `tmp_odo_test.py`.

## Workflow — agregar un endpoint backend

Sigue este orden. Saltárselo casi siempre produce blueprints mal registrados o rutas que no responden.

1. **Definir el dominio**. ¿Encaja en un blueprint existente (`routes/<dominio>.py`)? Si sí, añade ahí. Si es un dominio nuevo, crea `routes/<nuevo>.py` con el patrón estándar:
   ```python
   from flask import Blueprint, request, jsonify
   import logging
   <nuevo>_bp = Blueprint('<nuevo>', __name__, url_prefix='')
   ```
2. **Modelo de datos**. Si toca MySQL, escribe queries en `models/<nuevo>_model.py` usando `db_conexion.obtener_conexion()`. Si toca Odoo, usa `utils.odoo_utils.get_odoo_models()`.
3. **Ruta**. Implementa la función con validación de payload, autenticación JWT, try/except con logging, y respuesta `jsonify(...), <status>`.
4. **Registrar el blueprint**. Agrega el import y `app.register_blueprint(<nuevo>_bp)` en `app.py` dentro de `create_app()`. Si lo olvidas, la ruta existe pero Flask responde 404.
5. **Test**. Crea `tests/test_<nuevo>.py` mockeando dependencias externas.
6. **CORS**. Si el frontend llama desde un dominio nuevo, agrégalo a `allowed_origins`.

Lee `references/backend.md` para el esqueleto completo con un ejemplo.

## Workflow — agregar un service/component Angular

1. **Service**. `ng generate service services/<dominio>` o crear manualmente con el patrón de `src/app/services/monitor-odoo.service.ts`: `@Injectable({providedIn: 'root'})`, `environment.apiUrl`, `HttpClient`, caché con `BehaviorSubject` o `shareReplay` donde aplique.
2. **Spec**. El `.spec.ts` se genera automáticamente con `ng generate`. Si lo creaste a mano, añádelo con `HttpClientTestingModule` y un test por cada método público.
3. **Consumir en el component**. Inyecta el service, suscríbete con `async` pipe en la plantilla cuando sea posible para evitar fugas de memoria. Si usas `.subscribe()`, guarda la `Subscription` y desuscribe en `ngOnDestroy`.
4. **Tipar respuestas**. Define una interface para la respuesta del backend en `src/app/models/` (o junto al service) y tipa `HttpClient.get<MiTipo>()`.
5. **Rutas**. Si es una vista nueva, regístrala en `src/app/app.routes.ts` con su guard correspondiente si aplica.

Lee `references/angular.md` para el esqueleto completo.

## Workflow — integrar un modelo Odoo nuevo

1. Autentícate con `uid, models, err = get_odoo_models()`. Si `uid` es falsy, devuelve error con el `err` loggeado (sin exponer el traceback al cliente).
2. Si no conoces los campos, llama primero a `models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, '<modelo>', 'fields_get', [], {})` para listarlos.
3. Construye el domain empezando por `('company_id', '=', ODOO_COMPANY_ID)` cuando aplique.
4. Usa `search_read` con `fields` explícito (nunca traigas todos los campos).
5. Si vas a leer relaciones (líneas de orden, movimientos, pagos), acumula IDs y haz una sola lectura por modelo relacionado.

Lee `references/odoo.md` para el catálogo de modelos más usados en el proyecto y snippets listos.

## Referencias

Lee la referencia correspondiente cuando la tarea profundice en ese dominio:

- `references/odoo.md` — Autenticación, modelos usados, dominios comunes, anti-patrones, snippets reutilizables.
- `references/backend.md` — Plantilla de blueprint, patrón MySQL, Celery tasks, logging, configuración.
- `references/angular.md` — Plantilla de service con caché, component, interceptor JWT, guard, proxy.
- `references/testing.md` — Plantillas pytest (con mocks de Odoo/MySQL) y Jasmine (`HttpClientTestingModule`).
- `references/security.md` — JWT, CORS, .env, multi-empresa, checklist antes de commit.

## Reglas de estilo

- Idioma: comentarios en español (consistente con el código existente), identificadores en inglés o español según la convención local del archivo — no mezcles.
- Mensajes de error al cliente: en español, claros, sin stack traces.
- Imports: primero stdlib, luego terceros, luego locales. Una línea en blanco entre grupos.
- No agregues dependencias nuevas sin justificarlo con el usuario — el stack ya resuelve casi todo.
