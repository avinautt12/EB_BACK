from flask import Blueprint, jsonify
from models.monitor_odoo_model import obtener_todos_los_registros

monitor_odoo_bp = Blueprint('monitor_odoo', __name__, url_prefix='/monitor_odoo')

@monitor_odoo_bp.route('/', methods=['GET'])
def listar():
    datos = obtener_todos_los_registros()
    return jsonify(datos)
