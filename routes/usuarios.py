from flask import Blueprint, jsonify
from models.user_model import obtener_usuarios

usuarios_bp = Blueprint('usuarios', __name__, url_prefix='/usuarios')

@usuarios_bp.route('/', methods=['GET'])
def listar_usuarios():
    try:
        usuarios = obtener_usuarios()
        return jsonify(usuarios), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
