import io
import logging

from flask import Blueprint, jsonify, make_response, send_file

from services.garantias_service import exportar_excel, get_dashboard_data, invalidar_cache

garantias_bp = Blueprint("garantias", __name__, url_prefix="/garantias")


@garantias_bp.route("/dashboard", methods=["GET"])
def dashboard():
    try:
        data = get_dashboard_data()
        return jsonify(data)
    except Exception as e:
        logging.exception("Error en /garantias/dashboard: %s", e)
        return jsonify({"error": "Error al obtener datos de garantías"}), 500


@garantias_bp.route("/exportar", methods=["GET"])
def exportar():
    try:
        excel_bytes = exportar_excel()
        buf = io.BytesIO(excel_bytes)
        buf.seek(0)
        return send_file(
            buf,
            as_attachment=True,
            download_name="garantias.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        logging.exception("Error al exportar garantías Excel: %s", e)
        return jsonify({"error": "Error al generar Excel"}), 500


@garantias_bp.route("/refrescar", methods=["POST"])
def refrescar():
    """Invalida el caché para forzar recarga del Google Sheet."""
    invalidar_cache()
    return jsonify({"ok": True, "mensaje": "Caché invalidado"})
