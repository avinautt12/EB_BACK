# routes/permisos_bp.py

from flask import Blueprint, request, jsonify
from services.permisos_service import PermisosService

permisos_bp = Blueprint('permisos', __name__, url_prefix='/api/permisos')

@permisos_bp.route('/delegables', methods=['GET'])
def obtener_delegables():
    """Obtiene los módulos y acciones que un administrador puede delegar a sus hijos."""
    try:
        padre_id = request.args.get('padre_id', type=int)
        if not padre_id:
            return jsonify({"error": "El parámetro padre_id es requerido."}), 400
            
        permisos = PermisosService.obtener_permisos_delegables(padre_id)
        return jsonify({"permisos_delegables": permisos}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@permisos_bp.route('/usuario/<int:hijo_id>', methods=['GET'])
def obtener_permisos_usuario(hijo_id):
    """Obtiene la lista de permisos asignados actualmente a un usuario hijo."""
    try:
        padre_id = request.args.get('padre_id', type=int)
        if not padre_id:
            return jsonify({"error": "El parámetro padre_id es requerido."}), 400
            
        permisos = PermisosService.obtener_permisos_usuario(padre_id, hijo_id)
        return jsonify({"permisos": permisos}), 200
    except Exception as e:
        msg = str(e)
        status_code = 403 if "Acceso denegado" in msg else 500
        return jsonify({"error": msg}), status_code


@permisos_bp.route('/asignar', methods=['POST'])
def asignar_permiso():
    """Asigna un permiso específico a un usuario hijo aplicando las reglas de seguridad."""
    try:
        data = request.get_json() or {}
        padre_id = data.get('padre_id')
        hijo_id = data.get('hijo_id')
        modulo_id = data.get('modulo_id')
        accion_id = data.get('accion_id')
        
        if not all([padre_id, hijo_id, modulo_id, accion_id]):
            return jsonify({"error": "Faltan parámetros requeridos (padre_id, hijo_id, modulo_id, accion_id)."}), 400
            
        resultado = PermisosService.asignar_permiso_hijo(padre_id, hijo_id, modulo_id, accion_id)
        return jsonify(resultado), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 403


@permisos_bp.route('/revocar', methods=['DELETE'])
def revocar_permiso():
    """Revoca un permiso asignado a un usuario hijo."""
    try:
        data = request.get_json() or {}
        padre_id = data.get('padre_id')
        hijo_id = data.get('hijo_id')
        modulo_id = data.get('modulo_id')
        accion_id = data.get('accion_id')

        if not all([padre_id, hijo_id, modulo_id, accion_id]):
            return jsonify({"error": "Faltan parámetros requeridos (padre_id, hijo_id, modulo_id, accion_id)."}), 400

        resultado = PermisosService.revocar_permiso_hijo(padre_id, hijo_id, modulo_id, accion_id)
        return jsonify(resultado), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 403