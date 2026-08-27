# routes/usuarios_hijos_bp.py

from flask import Blueprint, request, jsonify
from services.usuarios_hijos_service import UsuariosHijosService

usuarios_hijos_bp = Blueprint('usuarios_hijos', __name__, url_prefix='/api/usuarios-hijos')

@usuarios_hijos_bp.route('/cupo', methods=['GET'])
def obtener_cupo():
    """Obtiene el cupo actual de usuarios permitidos para el administrador."""
    try:
        padre_id = request.args.get('padre_id', type=int)
        if not padre_id:
            return jsonify({"error": "El parámetro padre_id es requerido."}), 400

        cupo = UsuariosHijosService.obtener_cupo_padre(padre_id)
        return jsonify(cupo), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@usuarios_hijos_bp.route('', methods=['GET'])
def listar_hijos():
    """Lista todos los usuarios hijos pertenecientes al padre."""
    try:
        padre_id = request.args.get('padre_id', type=int)
        if not padre_id:
            return jsonify({"error": "El parámetro padre_id es requerido."}), 400

        hijos = UsuariosHijosService.listar_hijos(padre_id)
        return jsonify({"usuarios": hijos}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@usuarios_hijos_bp.route('', methods=['POST'])
def crear_hijo():
    """Crea un usuario hijo verificando disponibilidad de cupo."""
    try:
        data = request.get_json() or {}
        padre_id = data.get('padre_id')

        if not padre_id:
            return jsonify({"error": "El campo padre_id es requerido."}), 400

        campos_requeridos = ['nombre', 'correo', 'usuario', 'contrasena']
        for campo in campos_requeridos:
            if not data.get(campo):
                return jsonify({"error": f"El campo {campo} es obligatorio."}), 400

        resultado = UsuariosHijosService.crear_usuario_hijo(padre_id, data)
        return jsonify(resultado), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@usuarios_hijos_bp.route('/<int:hijo_id>/contrasena', methods=['PUT'])
def cambiar_contrasena(hijo_id):
    """Cambia la contraseña de un usuario hijo."""
    try:
        data = request.get_json() or {}
        padre_id = data.get('padre_id')
        nueva_contrasena = data.get('contrasena')

        if not padre_id or not nueva_contrasena:
            return jsonify({"error": "Los campos padre_id y contrasena son obligatorios."}), 400

        resultado = UsuariosHijosService.cambiar_contrasena_hijo(padre_id, hijo_id, nueva_contrasena)
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@usuarios_hijos_bp.route('/<int:hijo_id>/estado', methods=['PUT'])
def cambiar_estado(hijo_id):
    """Activa o desactiva un usuario hijo."""
    try:
        data = request.get_json() or {}
        padre_id = data.get('padre_id')
        nuevo_estado = data.get('activo')

        if padre_id is None or nuevo_estado is None:
            return jsonify({"error": "Los campos padre_id y activo (1 o 0) son obligatorios."}), 400

        resultado = UsuariosHijosService.cambiar_estado_hijo(padre_id, hijo_id, int(nuevo_estado))
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
@usuarios_hijos_bp.route('/<int:hijo_id>', methods=['DELETE'])
def eliminar_hijo(hijo_id):
    """Elimina físicamente un usuario hijo previa validación del padre."""
    try:
        padre_id = request.args.get('padre_id', type=int)
        if not padre_id:
            data = request.get_json() or {}
            padre_id = data.get('padre_id')
            
        if not padre_id:
            return jsonify({"error": "El parámetro padre_id es requerido."}), 400
            
        resultado = UsuariosHijosService.eliminar_usuario_hijo(padre_id, hijo_id)
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
@usuarios_hijos_bp.route('/correo-padre/<int:padre_id>', methods=['GET'])
def obtener_correo_padre(padre_id):
    """Endpoint dedicado a devolver el correo del administrador."""
    try:
        resultado = UsuariosHijosService.obtener_correo_padre(padre_id)
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500