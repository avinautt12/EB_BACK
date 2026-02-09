import eventlet
eventlet.monkey_patch()  # Debe estar al inicio del archivo

from flask import Flask
from flask_cors import CORS
from socket_instance import socketio

# --- BLUEPRINTS EXISTENTES ---
from routes.monitor_odoo import monitor_odoo_bp
from routes.auth import auth
from routes.usuarios import usuarios_bp
from routes.clientes import clientes_bp
from routes.metas import metas_bp
from routes.previo import previo_bp
from routes.proyecciones import proyecciones_bp
from routes.disponible import disponibilidad_bp
from routes.multimarcas import multimarcas_bp
from routes.caratulas import caratulas_bp
from routes.integrales import integrales_bp
from routes.email import email_bp

# --- NUEVOS BLUEPRINTS (Traídos de tu local) ---
from routes.ordenes_compra import ordenes_compra_bp
from routes.dashboard_flujo import dashboard_flujo_bp
from routes.logistica import logistica_bp
from routes.gastos import gastos_bp
from routes.ingresos import ingresos_bp

# Importamos la instancia de Celery desde celery_worker
from celery_worker import celery_app as celery

def create_app():
    app = Flask(__name__)

    # Vinculamos y configuramos Celery después de crear la app
    celery.conf.update(
        broker_url=app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
        result_backend=app.config.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    )
    celery.Task = type('Task', (celery.Task,), {'__call__': lambda self, *args, **kwargs: self.run(*args, **kwargs)})

    # Configuración CORS
    allowed_origins = [
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "http://3.128.54.77",
        "http://3.146.204.64",
        "https://app.elite-bike.com",
        "https://api.elite-bike.com"
    ]

    CORS(app, resources={
        r"/*": {
            "origins": allowed_origins,
            "supports_credentials": True,
            "expose_headers": ["Content-Disposition", "Content-Type"],
            "allow_headers": ["Authorization", "Content-Type"]
        }
    })

     # Configuración Socket.IO con async_mode explícito
    socketio.init_app(
        app,
        cors_allowed_origins=allowed_origins,
        async_mode='eventlet',
        logger=True,
        engineio_logger=True,
        path='/socket.io/'
    )

    # --- REGISTRO DE BLUEPRINTS ---
    
    # Viejos
    app.register_blueprint(monitor_odoo_bp)
    app.register_blueprint(auth)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(clientes_bp)
    app.register_blueprint(metas_bp)
    app.register_blueprint(previo_bp)
    app.register_blueprint(proyecciones_bp)
    app.register_blueprint(disponibilidad_bp)
    app.register_blueprint(multimarcas_bp)
    app.register_blueprint(caratulas_bp)
    app.register_blueprint(integrales_bp)
    app.register_blueprint(email_bp)

    # Nuevos (Agregados aquí)
    app.register_blueprint(ordenes_compra_bp)
    app.register_blueprint(dashboard_flujo_bp)
    app.register_blueprint(logistica_bp)
    app.register_blueprint(gastos_bp)
    app.register_blueprint(ingresos_bp)

    return app

app = create_app()

if __name__ == '__main__':
    # Usamos socketio.run para mantener compatibilidad con eventlet en el servidor
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False,  # Importante para eventlet
        log_output=True
    )