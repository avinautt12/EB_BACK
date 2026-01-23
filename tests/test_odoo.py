import xmlrpc.client
import ssl

url = 'https://ebik.odoo.com/'
db = 'ebik-prod-15375115'
username = 'sistemas@elitebike-mx.com'
password = 'bb36fdae62c3c113fb91de0143eba06da199672d'

print("Intentando conectar...")

try:
    context = ssl._create_unverified_context()
    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url), context=context)
    
    # Intentamos autenticar
    uid = common.authenticate(db, username, password, {})
    
    if uid:
        print(f"✅ ¡ÉXITO! Conexión establecida. Tu User ID es: {uid}")
    else:
        print("❌ Falló la autenticación. Revisa usuario o API Key.")

except Exception as e:
    print(f"❌ Error de conexión: {e}")