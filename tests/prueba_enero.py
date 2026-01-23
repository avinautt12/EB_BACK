import xmlrpc.client
import ssl

# --- TUS CREDENCIALES ---
url = 'https://ebik.odoo.com/'
db = 'ebik-prod-15375115'
username = 'sistemas@elitebike-mx.com'
password = 'bb36fdae62c3c113fb91de0143eba06da199672d'

NOMBRE_DIARIO = '00000752'

print(f"--- Buscando configuración del diario: {NOMBRE_DIARIO} ---")

try:
    context = ssl._create_unverified_context()
    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url), context=context)
    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url), context=context)
    uid = common.authenticate(db, username, password, {})

    if not uid:
        print("❌ Error de login")
        exit()

    # 1. Buscamos el Diario (Journal) por nombre
    journal_ids = models.execute_kw(db, uid, password, 
        'account.journal', 'search', 
        [[('name', 'ilike', NOMBRE_DIARIO)]] # ilike busca aunque haya mayusculas/minusculas
    )

    if not journal_ids:
        print(f"❌ No encontré ningún diario llamado '{NOMBRE_DIARIO}'")
        exit()

    # 2. Leemos la configuración del diario para ver su cuenta por defecto
    journals = models.execute_kw(db, uid, password,
        'account.journal', 'read',
        [journal_ids],
        {'fields': ['name', 'default_account_id', 'type']}
    )

    for j in journals:
        print(f"\n🔎 ENCONTRADO: {j['name']} (Tipo: {j['type']})")
        
        # default_account_id viene como [ID, "Nombre Cuenta"]
        cuenta_info = j['default_account_id'] 
        
        if cuenta_info:
            cuenta_id = cuenta_info[0]
            
            # 3. Vamos a buscar el CÓDIGO de esa cuenta ID
            cuentas = models.execute_kw(db, uid, password,
                'account.account', 'read',
                [[cuenta_id]],
                {'fields': ['code', 'name']}
            )
            
            codigo_real = cuentas[0]['code']
            nombre_real = cuentas[0]['name']
            
            print(f"✅ LA CUENTA CONTABLE REAL ES: {codigo_real}")
            print(f"   Nombre: {nombre_real}")
            print(f"👉 DEBES USAR ESTE CÓDIGO EN TU BASE DE DATOS: {codigo_real}")
        else:
            print("⚠️ Este diario no tiene cuenta por defecto configurada.")

except Exception as e:
    print(f"Error: {e}")