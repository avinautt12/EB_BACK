from flask import Blueprint, jsonify, request
from utils.otp_utils import (
    generar_otp, verificar_otp, otp_activo, listar_tokens_usuarios,
    sincronizar_usuarios_desde_monitor, TIPOS_VALIDOS, listar_tokens_usuarios_monitor
)

edicion_bp = Blueprint('edicion', __name__, url_prefix='/edicion')


@edicion_bp.route('/generar-otp', methods=['POST'])
def generar():
    data = request.get_json() or {}
    usuario_id = data.get('usuario_id')
    tipo = data.get('tipo', 'super')
    if not usuario_id:
        return jsonify({'error': 'usuario_id requerido'}), 400
    if tipo not in TIPOS_VALIDOS:
        return jsonify({'error': f'tipo inválido. Valores aceptados: {", ".join(TIPOS_VALIDOS)}'}), 400
    codigo = generar_otp(int(usuario_id), tipo=tipo)
    return jsonify({'codigo': codigo, 'tipo': tipo})


@edicion_bp.route('/otp-activo', methods=['GET'])
def ver_otp_activo():
    usuario_id = request.args.get('usuario_id', type=int)
    tipo = request.args.get('tipo', None)
    otp = otp_activo(usuario_id, tipo)
    if otp:
        return jsonify(otp)
    return jsonify({'codigo': None})


@edicion_bp.route('/tokens', methods=['GET'])
def listar_tokens():
    """Lista todos los usuarios (no-admin) con sus tokens activos por tipo."""
    return jsonify(listar_tokens_usuarios())


@edicion_bp.route('/tokens-monitor', methods=['GET'])
def listar_tokens_monitor():
    """Lista TODOS los usuarios visibles en Monitor de Pedidos con sus tokens activos."""
    return jsonify(listar_tokens_usuarios_monitor())


@edicion_bp.route('/verificar-otp', methods=['POST'])
def verificar():
    data = request.get_json() or {}
    codigo = str(data.get('codigo', '')).strip()
    if not codigo:
        return jsonify({'valid': False, 'error': 'Código requerido'}), 400
    tipo = verificar_otp(codigo)
    if tipo:
        return jsonify({'valid': True, 'tipo': tipo})
    return jsonify({'valid': False, 'error': 'Código inválido o expirado'}), 401


@edicion_bp.route('/sincronizar-desde-monitor', methods=['POST'])
def sincronizar():
    """Pre-genera OTP super para TODOS los usuarios visibles en Monitor de Pedidos."""
    result = sincronizar_usuarios_desde_monitor()
    return jsonify(result), 200
