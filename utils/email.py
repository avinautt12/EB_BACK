import smtplib
from email.mime.text import MIMEText

def enviar_correo_activacion(destinatario, codigo):
    remitente = "avinaluciano50@gmail.com"
    contrasena = "onep sobi teur pdds"  
    asunto = "Código de activación"
    cuerpo = f"Tu código de activación es: {codigo}"

    mensaje = MIMEText(cuerpo, "plain")
    mensaje["Subject"] = asunto
    mensaje["From"] = remitente
    mensaje["To"] = destinatario

    try:
        servidor = smtplib.SMTP("smtp.gmail.com", 587)
        servidor.starttls()
        servidor.login(remitente, contrasena)
        servidor.sendmail(remitente, destinatario, mensaje.as_string())
        servidor.quit()
    except Exception as e:
        print(f"Error al enviar correo: {e}")
        raise e
