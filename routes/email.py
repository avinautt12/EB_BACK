from flask import Blueprint, request, jsonify
import os
from datetime import datetime
import jwt
from datetime import timedelta
from db_conexion import obtener_conexion

from utils.email_utils import (
    obtener_credenciales_por_usuario,
    guardar_historial_inicial,
    obtener_nombre_usuario,
)

from celery_worker import enviar_caratula_pdf_async

email_bp = Blueprint('email', __name__, url_prefix='')

@email_bp.route('/email/enviar-caratura-pdf', methods=['POST'])
def enviar_caratula_pdf():
    """Endpoint para enviar carátula por email de forma asíncrona."""
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    
    try:
        data = request.get_json()
        
        required_fields = ['to', 'cliente_nombre', 'clave', 'datos_caratula']
        if not all(field in data for field in required_fields):
            return jsonify({"error": f"Faltan campos requeridos: {', '.join(required_fields)}"}), 400

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Token de autorización requerido"}), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            decoded_token = jwt.decode(token, options={"verify_signature": False})
            usuario = decoded_token.get('usuario', '')
            nombre_usuario_envio = obtener_nombre_usuario(usuario)
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido"}), 401

        credenciales = obtener_credenciales_por_usuario(usuario)
        gmail_user = credenciales['user']

        historial_id = guardar_historial_inicial(
            usuario=usuario,
            nombre_usuario=nombre_usuario_envio,
            correo_remitente=gmail_user,
            correo_destinatario=data['to'],
            cliente_nombre=data['cliente_nombre'],
            clave_cliente=data['clave']
        )
        
        if historial_id:
            enviar_caratula_pdf_async.delay(data, usuario, historial_id)
        
        return jsonify({
            "mensaje": "El correo se está procesando en segundo plano.",
            "status": "tarea_enviada",
            "historial_id": historial_id
        }), 202

    except Exception as e:
        print(f"Error al procesar la solicitud: {str(e)}")
        return jsonify({"error": f"Error al procesar la solicitud: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()
    
@email_bp.route('/email/configuracion', methods=['GET'])
def obtener_configuracion_email():
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    
    """Obtener configuración de email basada en el usuario autenticado"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Token de autorización requerido"}), 401
            
        token = auth_header.split(' ')[1]
        
        decoded_token = jwt.decode(token, options={"verify_signature": False})
        usuario = decoded_token.get('usuario', '')
        
        credenciales = obtener_credenciales_por_usuario(usuario)
        gmail_user = credenciales['user']
        
        return jsonify({
            "configurado": bool(gmail_user),
            "email_remitente": gmail_user,
            "usuario_actual": usuario
        }), 200
        
    except Exception as e:
        return jsonify({
            "configurado": False,
            "error": f"No se pudo determinar la configuración: {str(e)}"
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

@email_bp.route('/email/historial-caratulas', methods=['GET'])
def obtener_historial_caratulas():
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT id, nombre_usuario, usuario_envio, correo_remitente, correo_destinatario,
                       cliente_nombre, clave_cliente, fecha_envio, hora_envio, estado
                FROM historial_caratulas
                ORDER BY fecha_envio DESC, hora_envio DESC
            """)
            historial = cursor.fetchall()
            columnas = [desc[0] for desc in cursor.description]

            resultado = []
            for fila in historial:
                fila_dict = dict(zip(columnas, fila))
                for key, value in fila_dict.items():
                    if isinstance(value, timedelta):
                        fila_dict[key] = str(value)
                resultado.append(fila_dict)

        return jsonify(resultado), 200
    except Exception as e:
        print(f"Error al obtener historial: {str(e)}")
        return jsonify({"error": f"Error al obtener el historial: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

