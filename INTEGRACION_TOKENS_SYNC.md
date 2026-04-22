"""
INTEGRACIÓN SUGERIDA: Sincronización Automática de Tokens en app.py

Este archivo contiene ejemplos de cómo integrar la sincronización automática
de usuarios del Monitor de Pedidos con Tokens de Edición en tu aplicación Flask.

Elige UNO de los enfoques abajo según tu necesidad.
"""

# ============================================================================
# OPCIÓN 1: Sincronización al iniciar la aplicación (MÁS SIMPLE)
# ============================================================================
"""
DÓNDE: Al final de app.py, después de crear la app Flask
CUÁNDO: Se ejecuta UNA SOLA VEZ al iniciar el servidor

VENTAJAS:
  + Simple, no requiere Celery
  + Asegura tokens frescos al iniciar
  
DESVENTAJAS:
  - Solo se ejecuta al iniciar (no diario)
  - Ralentiza el startup si hay muchos usuarios
"""

# En app.py:

from flask import Flask
from utils.otp_utils import sincronizar_usuarios_desde_monitor

app = Flask(__name__)

# ... resto de configuración ...

# Sincronizar tokens al iniciar
@app.before_request
def init_sync_tokens():
    # Solo hacer esto UNA SOLA VEZ (en primer request)
    if not hasattr(init_sync_tokens, 'done'):
        init_sync_tokens.done = True
        print("🔄 Sincronizando tokens del Monitor en startup...")
        try:
            result = sincronizar_usuarios_desde_monitor()
            print(f"✅ Sincronización al iniciar: {result['sincronizados']}/{result['total_monitor']} usuarios")
        except Exception as e:
            print(f"⚠️  Error en sincronización de startup: {e}")

# if __name__ == '__main__':
#     app.run(debug=False)


# ============================================================================
# OPCIÓN 2: Sincronización Diaria (RECOMENDADO)
# ============================================================================
"""
DÓNDE: Al final de app.py, después de crear la app Flask
CUÁNDO: Se ejecuta diariamente a las 00:00 (o la hora que definas)

VENTAJAS:
  + No ralentiza startup
  + Se ejecuta automáticamente cada día
  + Tokens siempre frescos
  
DESVENTAJAS:
  - Requiere Celery + Redis/RabbitMQ
  - Más complejo de configurar
"""

# En app.py:

from flask import Flask
from celery import Celery
from utils.otp_utils import sincronizar_usuarios_desde_monitor

app = Flask(__name__)

# Configurar Celery
def make_celery(app):
    celery = Celery(app.import_name, backend='redis://localhost:6379', broker='redis://localhost:6379')
    celery.conf.update(app.config)
    return celery

celery = make_celery(app)

# Tarea de Celery para sincronización diaria
@celery.task
def sincronizar_tokens_diarios():
    """Sincroniza tokens cada día a las 00:00"""
    print("🔄 Ejecutando sincronización diaria de tokens...")
    try:
        result = sincronizar_usuarios_desde_monitor()
        print(f"✅ Sincronización diaria: {result['sincronizados']}/{result['total_monitor']} usuarios")
        return {
            "status": "success",
            "sincronizados": result['sincronizados'],
            "errores": result['errores']
        }
    except Exception as e:
        print(f"❌ Error en sincronización diaria: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

# Configurar Celery Beat Schedule
from celery.schedules import crontab

app.conf.beat_schedule = {
    'sincronizar-tokens-diarios': {
        'task': '__main__.sincronizar_tokens_diarios',
        'schedule': crontab(hour=0, minute=0),  # 00:00 cada día
    },
    'sincronizar-tokens-cada-6-horas': {
        # Si lo prefieres cada 6 horas en lugar de diario:
        'task': '__main__.sincronizar_tokens_diarios',
        'schedule': crontab(minute=0, hour='*/6'),  # 00:00, 06:00, 12:00, 18:00
    },
}

# Para ejecutar Celery Beat:
# celery -A app beat --loglevel=info

# En otra terminal:
# celery -A app worker --loglevel=info


# ============================================================================
# OPCIÓN 3: Endpoint Manual + Cron Job (OPCIÓN INTERMEDIA)
# ============================================================================
"""
DÓNDE: En una ruta protegida (solo admin) en app.py o en una tarea cron del SO
CUÁNDO: Se ejecuta manualmente por admin O vía cron job del sistema operativo

VENTAJAS:
  + Control manual sobre la sincronización
  + No requiere Celery
  + Endpoint visible en API docs
  
DESVENTAJAS:
  - Requiere coordinación manual o script cron
  - El endpoint debe estar protegido (agregar auth)
"""

# En app.py (agregar ruta):

from flask import Blueprint, jsonify
from utils.otp_utils import sincronizar_usuarios_desde_monitor

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/sincronizar-edicion-tokens', methods=['POST'])
def sincronizar_tokens_admin():
    """
    Endpoint solo para admins que ejecuta sincronización de tokens.
    
    ⚠️  IMPORTANTE: Agregar decorador @login_required o similar para proteger
    """
    # TODO: Agregar validación de admin:
    # @login_required
    # if not current_user.is_admin: return forbidden()
    
    result = sincronizar_usuarios_desde_monitor()
    return jsonify(result), 200

# Registrar blueprint en app:
# app.register_blueprint(admin_bp)

# Uso vía curl:
# curl -X POST http://localhost:5000/admin/sincronizar-edicion-tokens


# En crontab del servidor (Linux/Mac):
# 0 0 * * * /usr/bin/python3 /path/to/sync_tokens_desde_monitor.py >> /var/log/sync_tokens.log 2>&1


# ============================================================================
# OPCIÓN 4: Endpoint Público + Rate Limiting (MENOS RECOMENDADO)
# ============================================================================
"""
DÓNDE: Ruta pública pero con rate limiting
CUÁNDO: Cualquiera puede llamarlo pero con límite de frecuencia

VENTAJAS:
  + Accesible desde UI sin auth
  + Simple de integrar
  
DESVENTAJAS:
  - Security risk si no está bien protegido
  - Posible abuso
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@app.route('/edicion/sincronizar-desde-monitor', methods=['POST'])
@limiter.limit("1 per minute")  # Máximo 1 sincronización por minuto
def sincronizar():
    """Sincronización pública con rate limiting"""
    result = sincronizar_usuarios_desde_monitor()
    return jsonify(result), 200


# ============================================================================
# RECOMENDACIÓN FINAL
# ============================================================================
"""
Para tu caso de uso, recomiendo:

🏆 MEJOR: Opción 2 (Sincronización Diaria con Celery)
   - Confiable
   - Automática
   - No ralentiza app
   
💡 SI NO TIENES CELERY: Opción 3 (Endpoint + Cron)
   - Configurable
   - Simple
   - Requiere script cron del SO

⚡ RÁPIDO: Opción 1 (Sincronización al iniciar)
   - Inmediato
   - Sin dependencias
   - Pero limitado
   
❌ NO RECOMENDADO: Opción 4 (Público)
   - Risk de seguridad
   - Puede causar problemas
"""

# ============================================================================
# VERIFICACIÓN POST-INTEGRACIÓN
# ============================================================================
"""
Después de agregar cualquiera de las opciones arriba, prueba:

1. Iniciar la app:
   python app.py

2. En otra terminal, validar:
   python validate_tokens_sync.py

3. Verificar que:
   - ✅ Tabla 'otps' existe
   - ✅ Usuarios en Monitor están sincronizados
   - ✅ Tokens se generaron correctamente

4. Revisar logs para confirmar ejecución:
   - grep "Sincronización" app.log
   - grep "✅" app.log
"""
