from flask import Flask
from flask_cors import CORS
from socket_instance import socketio

from routes.monitor_odoo import monitor_odoo_bp
from routes.auth import auth 
from routes.usuarios import usuarios_bp
from routes.clientes import clientes_bp
from routes.metas import metas_bp
from routes.previo import previo_bp
from routes.proyecciones import proyecciones_bp
from routes.disponible import disponibilidad_bp

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["http://localhost:4200", "https://otro-dominio.com"]}}, supports_credentials=True)

socketio.init_app(app)  # IMPORTANTE

app.register_blueprint(monitor_odoo_bp)
app.register_blueprint(auth)
app.register_blueprint(usuarios_bp)
app.register_blueprint(clientes_bp)
app.register_blueprint(metas_bp)
app.register_blueprint(previo_bp)
app.register_blueprint(proyecciones_bp)
app.register_blueprint(disponibilidad_bp)

@socketio.on('connect')
def handle_connect():
    print('Cliente conectado')

@socketio.on('disconnect')
def handle_disconnect():
    print('Cliente desconectado')

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000, host='0.0.0.0')
