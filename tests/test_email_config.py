# tests/test_email_config.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def test_email_configuration():
    print("🔍 Probando configuración de email...")
    
    # Tus credenciales DIRECTAMENTE (para prueba)
    GMAIL_USER = 'sistemas@elitebike-mx.com'
    GMAIL_PASSWORD = 'yjtt fmca kbrr htar'  # Sin espacios
    
    print(f"📧 Usuario: {GMAIL_USER}")
    print(f"🔐 Password: {'***' + GMAIL_PASSWORD[-4:] if GMAIL_PASSWORD else 'No configurado'}")
    
    try:
        # Probando conexión SMTP
        print("🔄 Probando conexión con Gmail...")
        
        # Intentar con SSL primero (puerto 465)
        print("🔒 Intentando SSL (puerto 465)...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            print("✅ Conexión SSL exitosa!")
            
            # Probando envío de email de prueba
            print("📤 Probando envío de email...")
            msg = MIMEMultipart()
            msg['From'] = GMAIL_USER
            msg['To'] = GMAIL_USER  # Enviarse a sí mismo
            msg['Subject'] = 'Prueba de configuración - Elite Bikes'
            
            body = """
            <h3>✅ Configuración de Email Exitosa</h3>
            <p>Este es un email de prueba del sistema Elite Bikes.</p>
            <p>Si recibes este email, la configuración SMTP está funcionando correctamente.</p>
            """
            msg.attach(MIMEText(body, 'html'))
            
            server.send_message(msg)
            print("✅ Email de prueba enviado correctamente!")
            
        return True
        
    except smtplib.SMTPAuthenticationError as auth_error:
        print(f"❌ Error de autenticación: {auth_error}")
        print("\n🔍 Posibles soluciones:")
        print("1. ✅ Verifica que la verificación en 2 pasos esté ACTIVADA")
        print("2. ✅ Usa la CONTRASEÑA DE APLICACIÓN de 16 dígitos, no tu password normal")
        print("3. ✅ Asegúrate de no tener espacios en la contraseña")
        print("4. ✅ Verifica que el usuario esté correcto")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
        try:
            # Intentar con TLS como fallback (puerto 587)
            print("\n🔄 Intentando TLS (puerto 587)...")
            with smtplib.SMTP('smtp.gmail.com', 587, timeout=10) as server:
                server.starttls()
                server.login(GMAIL_USER, GMAIL_PASSWORD)
                print("✅ Conexión TLS exitosa!")
                return True
                
        except Exception as e2:
            print(f"❌ Error en TLS también: {e2}")
            
    return False

if __name__ == "__main__":
    print("=" * 50)
    print("TEST DE CONFIGURACIÓN DE EMAIL - ELITE BIKES")
    print("=" * 50)
    
    success = test_email_configuration()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 ¡CONFIGURACIÓN EXITOSA!")
        print("El sistema puede enviar emails correctamente.")
    else:
        print("💥 ERROR EN LA CONFIGURACIÓN")
        print("Revisa las credenciales y configuración de Gmail.")
    print("=" * 50)