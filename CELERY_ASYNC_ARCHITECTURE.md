# EB_BACK Celery & Async Architecture

Complete analysis of asynchronous task processing, message brokers, and async patterns in the repository.

---

## 1. CELERY CONFIGURATION

### Location: [`celery_worker.py`](celery_worker.py)

#### Broker & Backend
```python
# Message Broker: Redis
# Result Backend: Redis
redis_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
celery_app = Celery(__name__, broker=redis_url, backend=redis_url)
```

- **Broker URL**: Environment variable `CELERY_BROKER_URL`
- **Default**: `redis://localhost:6379/0`
- **Database**: Redis DB 0
- **Both broker and backend use Redis** (queue messages AND store task results)

#### Celery Configuration Settings
```python
celery_app.conf.update(
    task_serializer='json',           # JSON serialization for tasks
    accept_content=['json'],          # Accept only JSON content
    result_serializer='json',         # JSON serialization for results
    timezone='America/Mexico_City',   # Timezone for scheduling
    enable_utc=True,                  # Use UTC internally
    worker_hijack_root_logger=False,  # Don't override root logger
)
```

---

## 2. FLASK-CELERY INTEGRATION

### Location: [`app.py`](app.py) (lines 32-41)

```python
from celery_worker import celery_app as celery

def create_app():
    app = Flask(__name__)
    
    celery.conf.update(
        broker_url=app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
        result_backend=app.config.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    )
    celery.Task = type('Task', (celery.Task,), {
        '__call__': lambda self, *args, **kwargs: self.run(*args, **kwargs)
    })
```

- Celery instance is imported from `celery_worker.py`
- Configuration is updated to use Flask app config (or defaults to Redis)
- Task class is modified to allow custom execution behavior

---

## 3. CELERY TASKS DEFINED

### 📌 Task 1: PDF Caratula Email Generation & Sending

**Name**: `tasks.enviar_caratula_pdf_async`  
**File**: [`celery_worker.py`](celery_worker.py) (lines 77-155)  
**Decorator**: `@celery_app.task(name='tasks.enviar_caratula_pdf_async')`

#### Purpose
Generates a PDF caratula (cover sheet/invoice cover) and sends it via email asynchronously.

#### Parameters
```python
def enviar_caratula_pdf_async(data, usuario, historial_id):
    """
    data: dict          # Contains: to, cliente_nombre, clave, datos_caratula
    usuario: str        # User ID for retrieving SMTP credentials
    historial_id: int   # Database record ID for tracking email send status
    """
```

#### Workflow
1. **Generate HTML & PDF** (using `WeasyPrint`)
   - Calls `crear_cuerpo_email(data)` to generate HTML
   - Converts HTML to PDF using WeasyPrint library
   - Timing logged for performance monitoring

2. **Retrieve SMTP Connection** (from connection pool)
   - Calls `get_smtp_connection(usuario)` 
   - Returns pooled SMTP server + sender email
   - Reuses existing connections when possible
   - Automatic reconnection on disconnection

3. **Build Email Message**
   - Constructs MIME multipart message
   - Attaches HTML body (formatted email)
   - Attaches generated PDF with filename: `Caratula_{clave}_{date}.pdf`
   - Sets From, To, Subject headers

4. **Send Email**
   - Uses SMTP_SSL on port 465 to smtp.gmail.com
   - Sends via pooled connection
   - Updates database with 'Enviado' (Sent) status on success
   - Updates database with 'Fallido' (Failed) status on error

#### SMTP Connection Pool
```python
smtp_pool = {}        # usuario → smtplib.SMTP_SSL connection
smtp_users = {}       # usuario → gmail_user email address
```
- **Purpose**: Reuse SMTP connections to avoid reconnection overhead
- **Connection Check**: `noop()` command validates if connection is still alive
- **Credentials**: Retrieved from `obtener_credenciales_por_usuario(usuario)` (MySQL)
- **Port**: 465 (SMTP_SSL - more robust than 587 + STARTTLS)

#### Database Tracking
- Table: `historial_caratulas` (updated via `actualizar_estado_historial()`)
- Records: fecha_envio, hora_envio, estado (Enviado/Fallido)
- Logging: Detailed timing and error messages

---

## 4. HOW CELERY TASKS ARE INVOKED

### Location: [`routes/email.py`](routes/email.py)

#### Endpoint: `POST /email/enviar-caratura-pdf`

```python
@email_bp.route('/email/enviar-caratura-pdf', methods=['POST'])
def enviar_caratula_pdf():
    # ... validation and setup ...
    
    historial_id = guardar_historial_inicial(...)
    
    if historial_id:
        # ⭐ ASYNC TASK INVOCATION
        enviar_caratula_pdf_async.delay(data, usuario, historial_id)
    
    return jsonify({
        "mensaje": "El correo se está procesando en segundo plano.",
        "status": "tarea_enviada",
        "historial_id": historial_id
    }), 202  # 202 Accepted (task submitted, not completed)
```

#### Task Invocation Method
- **Method**: `.delay()` 
- **Returns**: Immediately (asynchronous)
- **Response**: HTTP 202 Accepted (task queued, not completed)
- **Client can poll**: Using `historial_id` to check email status

#### Request Flow
```
1. Client: POST /email/enviar-caratura-pdf
2. Flask: Validates token, saves historial_inicial record
3. Flask: Calls enviar_caratula_pdf_async.delay(...)
4. Celery: Enqueues task to Redis
5. Flask: Returns 202 with historial_id
6. Celery Worker: Picks up task from Redis queue
7. Worker: Generates PDF, sends email, updates status
8. Client: Can query /email/historial-caratulas to check status
```

#### Required Fields in Request
```json
{
    "to": "recipient@email.com",
    "cliente_nombre": "Client Name",
    "clave": "CLIENT_CODE",
    "datos_caratula": { /* caratula data */ }
}
```

#### Authentication
- **Required**: Bearer token in Authorization header
- **Token decoded** to extract `usuario` for SMTP credentials lookup
- **User's email** retrieved from credentials for "From" header

---

## 5. OTHER ASYNC PATTERNS (Non-Celery)

### A. THREADING (forecast.py)

**File**: [`routes/forecast.py`](routes/forecast.py)

#### Background Synchronization Task
```python
import threading

_catalogo_sync_lock = threading.Lock()
_catalogo_syncing = False

def _sync_catalogo_odoo_task():
    """Fetch all active product variants from Odoo and upsert into odoo_catalogo."""
    # Batch fetch products from Odoo via XML-RPC
    # Batch upsert into MySQL odoo_catalogo table
    
def _trigger_catalogo_sync(force: bool = False):
    global _catalogo_syncing
    with _catalogo_sync_lock:
        if _catalogo_syncing:
            return 'already_running'
        _catalogo_syncing = True
    
    t = threading.Thread(
        target=_sync_catalogo_odoo_task, 
        daemon=True, 
        name='catalogo_sync'
    )
    t.start()
```

- **Purpose**: Synchronize product catalog from Odoo to MySQL
- **Daemon Thread**: Runs in background, non-blocking
- **Lock Mechanism**: Prevents duplicate concurrent syncs
- **TTL Cache**: 3-minute cache for Odoo catalog queries
- **Auto-sync**: Triggered on app startup if catalog is empty
- **Batch Processing**: 500 products per batch to manage memory
- **Attributes**: Extracts color, talla (size) from Odoo product variants

#### Database
- **Table**: `odoo_catalogo`
- **Fields**: referencia_interna (PK), nombre_producto, categoria, marca, color, talla, actualizado_en
- **Indexes**: FULLTEXT on nombre_producto, INDEX on marca

---

### B. REDIS QUEUE (RQ) - WORKER.PY

**File**: [`worker.py`](worker.py)

```python
import redis
from rq import Worker, Queue, Connection

redis_conn = redis.Redis(host='localhost', port=6379, db=0)

if __name__ == '__main__':
    with Connection(redis_conn):
        worker = Worker(['emails'])
        print("🚀 Worker de emails iniciado. Esperando trabajos...")
        worker.work()
```

#### Purpose
- Separate worker process for email jobs
- Uses **RQ (Redis Queue)** instead of Celery
- **Note**: This appears to be an older/alternative implementation
- **Status**: May be deprecated in favor of Celery

#### Relationship to Celery
- Both use Redis as message broker
- RQ listens on queue named 'emails'
- Celery uses different queue names (default: 'celery')
- **These are separate systems** - tasks must be enqueued to correct one

---

### C. SOCKET.IO THREADING

**File**: [`app.py`](app.py) (lines 90-99)

```python
from flask_socketio import SocketIO

socketio.init_app(
    app,
    cors_allowed_origins=allowed_origins,
    async_mode='threading',  # use threading for async events
    logger=True,
    engineio_logger=True,
    path='/socket.io/'
)
```

- **Purpose**: Real-time bidirectional communication with frontend
- **Async Mode**: Threading (not eventlet or other)
- **Use Case**: Potentially for real-time dashboard updates
- **Note**: Eventlet monkey-patching is commented out (disabled for XML-RPC compatibility)

---

## 6. DEPENDENCIES (requirements.txt)

```
celery              # Async task queue library
redis               # Redis client (for Celery broker/backend)
rq                  # Redis Queue (alternative task queue)
eventlet            # Async I/O library (currently disabled)
flask-socketio      # WebSocket support for Flask
WeasyPrint          # HTML to PDF conversion for caratulas
```

---

## 7. ENVIRONMENT VARIABLES

**File**: [`.env`](.env)

### Currently Configured
- `ODOO_ENV`: Switches between 'test' and 'prod' Odoo instances
- Odoo credentials (URL, DB, user, password)

### Not Yet Configured (Uses Defaults)
- `CELERY_BROKER_URL`: Defaults to `redis://localhost:6379/0`
- `CELERY_RESULT_BACKEND`: Defaults to `redis://localhost:6379/0`

### To Enable Production Celery
```bash
# Add to .env:
CELERY_BROKER_URL=redis://PROD_REDIS_HOST:6379/0
CELERY_RESULT_BACKEND=redis://PROD_REDIS_HOST:6379/0
```

---

## 8. REDIS USAGE SUMMARY

| Component | Purpose | DB | Port |
|-----------|---------|-----|------|
| **Celery Broker** | Task queue (enqueue/dequeue) | 0 | 6379 |
| **Celery Result Backend** | Store task results | 0 | 6379 |
| **RQ (worker.py)** | Email job queue | 0 | 6379 |
| **Socket.IO** | May use Redis for session storage | varies | 6379 |

**⚠️ Note**: All using same Redis instance (DB 0) - could cause key collisions if not careful

---

## 9. TASK QUEUE FLOW DIAGRAM

```
┌─────────────┐
│   Frontend  │
└──────┬──────┘
       │ POST /email/enviar-caratura-pdf
       ▼
┌─────────────────────────────────────┐
│  Flask App (app.py)                 │
│  ├─ Validate token                  │
│  ├─ Save historial record           │
│  └─ enviar_caratula_pdf_async.delay()│
└──────┬──────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  Redis (Broker)                      │
│  Queue: celery (default)             │
│  Messages: JSON serialized           │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  Celery Worker (separate process)    │
│  ├─ Poll Redis for tasks             │
│  ├─ Deserialize JSON                 │
│  └─ Execute: enviar_caratula_pdf_async│
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  Task Execution                      │
│  ├─ Generate PDF (WeasyPrint)        │
│  ├─ Get SMTP connection (pooled)     │
│  ├─ Build email message              │
│  └─ Send via SMTP to Gmail           │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  Redis (Result Backend)              │
│  Stores: Task status, results        │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  MySQL (historial_caratulas)         │
│  Updates: estado (Enviado/Fallido)   │
└──────────────────────────────────────┘
```

---

## 10. RUNNING CELERY WORKERS

### Start a Celery Worker
```bash
cd /Users/jonathanpina/Desktop/REPOSITORIOS\ EB/EB_BACK

# Basic: Single worker on default queue
celery -A celery_worker worker --loglevel=info

# Production: Multiple workers, specific queue
celery -A celery_worker worker -Q celery -c 4 --loglevel=info

# With pool: threaded vs process-based
celery -A celery_worker worker --pool=threads -c 8
celery -A celery_worker worker --pool=prefork -c 4
```

### Monitor Tasks
```bash
# Real-time monitoring dashboard
celery -A celery_worker events

# Single task status
celery -A celery_worker inspect active
celery -A celery_worker inspect stats
```

### Purge Queue (if needed)
```bash
celery -A celery_worker purge
```

---

## 11. TASK HISTORY / LOGGING

### Where Tasks Are Logged
1. **Console Output**: Celery worker prints task lifecycle
2. **MySQL Database**: 
   - `historial_caratulas` table tracks email send status
   - Fields: usuario_envio, correo_remitente, correo_destinatario, estado, fecha_envio
3. **Application Logs**: Python logging module with timestamps

### Querying Email Status
```bash
curl -X GET "http://localhost:5000/email/historial-caratulas" \
  -H "Authorization: Bearer <token>"
```

Response includes:
- id, nombre_usuario, usuario_envio
- correo_remitente, correo_destinatario
- cliente_nombre, clave_cliente
- fecha_envio, hora_envio, **estado** (Enviado/Fallido)

---

## 12. POTENTIAL ISSUES & IMPROVEMENTS

### Current Issues
1. **Multiple Async Systems**: Celery + RQ + Threading = harder to maintain
2. **Single Redis DB**: All systems share DB 0 - risk of key collisions
3. **No Task Retry Logic**: Failed tasks don't retry (can add with `@celery_app.task(bind=True, max_retries=3)`)
4. **No Task Timeouts**: Tasks can hang indefinitely
5. **SMTP Pool Logic**: Global state could be problematic in multi-worker scenarios
6. **No Dead Letter Queue**: Failed tasks are lost (unless using result backend)
7. **Eventlet Disabled**: Because it conflicts with Odoo's XML-RPC

### Recommended Improvements
```python
# Add retries and timeout
@celery_app.task(
    name='tasks.enviar_caratula_pdf_async',
    bind=True,
    max_retries=3,
    time_limit=300,  # seconds
    soft_time_limit=280,
)
def enviar_caratula_pdf_async(self, data, usuario, historial_id):
    try:
        # ... existing code ...
    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

# Add dedicated Redis DB for each system
CELERY_BROKER_URL = 'redis://localhost:6379/1'  # Separate from RQ
RQ_REDIS_URL = 'redis://localhost:6379/2'      # Separate from Celery
```

---

## 13. SUMMARY TABLE

| Aspect | Value |
|--------|-------|
| **Primary Message Broker** | Redis (localhost:6379/0) |
| **Task Serialization** | JSON |
| **Timezone** | America/Mexico_City |
| **Active Celery Tasks** | 1 (`enviar_caratula_pdf_async`) |
| **Email Send Method** | SMTP_SSL (Gmail, port 465) |
| **Connection Pooling** | Yes (SMTP connection pool) |
| **Result Backend** | Redis |
| **Worker Type** | Celery (primary) + RQ (legacy) |
| **Async HTTP Response** | 202 Accepted |
| **Database Tracking** | MySQL `historial_caratulas` table |
| **Task Status Query** | `/email/historial-caratulas` endpoint |

---

## Files Summary

| File | Purpose |
|------|---------|
| [celery_worker.py](celery_worker.py) | Celery app, config, task definitions |
| [app.py](app.py) | Flask app, imports & configures Celery |
| [routes/email.py](routes/email.py) | Email endpoint that triggers Celery tasks |
| [worker.py](worker.py) | RQ worker (legacy) |
| [routes/forecast.py](routes/forecast.py) | Threading for Odoo catalog sync |
| [requirements.txt](requirements.txt) | Dependencies (celery, redis, etc.) |
| [.env](.env) | Environment variables (no Celery config yet) |
