from celery import Celery
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import base64
from datetime import datetime
import time
import logging

# Importa la librería para generar PDFs
from weasyprint import HTML

# Importa las funciones auxiliares de tu módulo de utilidades
from utils.email_utils import (
    obtener_credenciales_por_usuario,
    crear_cuerpo_email,
    actualizar_estado_historial,
)

# Configuración de Celery para usar Redis como intermediario
redis_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
celery_app = Celery(__name__, broker=redis_url, backend=redis_url)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Mexico_City',
    enable_utc=True,
    worker_hijack_root_logger=False,
)

# ----------------- POOL DE CONEXIONES SMTP -----------------
# Creamos un pool de conexiones global para reutilizar las conexiones SMTP
smtp_pool = {}

def get_smtp_connection(usuario):
    """Obtiene una conexión SMTP reutilizable para un usuario."""
    global smtp_pool
    # Primero, intentamos reutilizar la conexión si ya existe
    if usuario in smtp_pool:
        try:
            # Verificamos si la conexión sigue viva
            smtp_pool[usuario].noop()
            return smtp_pool[usuario]
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPException):
            logging.warning(f"Conexión SMTP para {usuario} perdida. Reestableciendo...")
            del smtp_pool[usuario] # La eliminamos si se perdió
    
    # Si no existe o se perdió, creamos una nueva conexión
    try:
        credenciales = obtener_credenciales_por_usuario(usuario)
        gmail_user = credenciales['user']
        gmail_password = credenciales['password']

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(gmail_user, gmail_password)
        smtp_pool[usuario] = server  # Guardamos la nueva conexión en el pool
        return server
    except Exception as e:
        logging.error(f"Error al establecer conexión SMTP para {usuario}: {e}")
        return None
# ----------------- FIN DEL POOL DE CONEXIONES SMTP -----------------

@celery_app.task(name='tasks.enviar_caratula_pdf_async')
def enviar_caratula_pdf_async(data, usuario, historial_id):
    """Tarea asíncrona que se encarga de generar el PDF y enviar el email."""
    try:
        logging.info(f"[{datetime.now()}] Tarea {historial_id} iniciada.")
        
        # --- Generar el HTML de la carátula y el PDF ---
        start_time = time.time()
        # La función ahora retorna un diccionario con ambos HTML
        htmls = crear_cuerpo_email(data) 
        
        # Usamos el HTML de la carátula para generar el PDF
        pdf_file = HTML(string=htmls['html_caratula_pdf']).write_pdf()
        logging.info(f"[{datetime.now()}] PDF generado en el backend en {time.time() - start_time:.2f} segundos.")
        
        # --- Obtener conexión del pool y enviar el mensaje ---
        start_time = time.time()
        server = get_smtp_connection(usuario)
        if not server:
            raise Exception("No se pudo obtener una conexión SMTP.")
        logging.info(f"[{datetime.now()}] Conexión SMTP obtenida en {time.time() - start_time:.2f} segundos.")

        msg = MIMEMultipart()
        msg['From'] = server.user
        msg['To'] = data['to']
        msg['Subject'] = f"Carátula - {data['cliente_nombre']} - {datetime.now().strftime('%d/%m/%Y')}"
        
        # Adjuntamos el HTML del cuerpo del email
        msg.attach(MIMEText(htmls['cuerpo_email_html'], 'html'))
        
        # Adjuntar el PDF generado
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(pdf_file)
        encoders.encode_base64(part)
        
        filename = f"Caratula_{data['clave']}_{datetime.now().strftime('%Y%m%d')}.pdf"
        part.add_header('Content-Disposition', f'attachment; filename={filename}')
        msg.attach(part)
        
        server.send_message(msg)
        logging.info(f"[{datetime.now()}] Email enviado en {time.time() - start_time:.2f} segundos.")

        actualizar_estado_historial(historial_id, 'Enviado')
        logging.info(f"[{datetime.now()}] Tarea {historial_id} finalizada con éxito.")
        
        return {"status": "success", "mensaje": "Email enviado correctamente."}

    except Exception as e:
        logging.error(f"[{datetime.now()}] Error en tarea {historial_id}: {str(e)}")
        actualizar_estado_historial(historial_id, 'Fallido')
        return {"status": "error", "mensaje": f"Error al enviar email: {str(e)}"}