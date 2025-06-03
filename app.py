from flask import Flask
from flask_cors import CORS

from routes.monitor_odoo import monitor_odoo_bp
from routes.auth import auth 
from routes.usuarios import usuarios_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(monitor_odoo_bp)
app.register_blueprint(auth)
app.register_blueprint(usuarios_bp)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
