import xmlrpc.client
import ssl

# --- CORRECCIÓN: USAMOS LA URL QUE SALE EN TU NAVEGADOR ---
url = 'https://ebik.odoo.com' 
db = 'ebik-prod-15375115'
username = 'sistemas@elitebike-mx.com'
password = 'bb36fdae62c3c113fb91de0143eba06da199672d' 

print("--- DESCARGANDO LISTA MAESTRA DE DIARIOS ---")

try:
    context = ssl._create_unverified_context()
    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url), context=context)
    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url), context=context)
    uid = common.authenticate(db, username, password, {})

    if not uid:
        print("❌ Error de login (Verifica contraseña/API Key)")
        exit()

    print(f"✅ Login exitoso (ID: {uid}). Descargando datos...")

    # 1. Traemos TODOS los diarios (sin filtros)
    journal_ids = models.execute_kw(db, uid, password, 'account.journal', 'search', [[]])
    
    # 2. Leemos sus datos
    journals = models.execute_kw(db, uid, password,
        'account.journal', 'read',
        [journal_ids],
        {'fields': ['name', 'code', 'type', 'default_account_id']}
    )

    print(f"\nSe encontraron {len(journals)} diarios.\n")
    print(f"{'DIARIO (NOMBRE)':<35} | {'CUENTA CONTABLE'}")
    print("-" * 80)

    for j in journals:
        nombre = j['name']
        cuenta_texto = "SIN CUENTA ASIGNADA"
        
        # Si tiene cuenta por defecto, sacamos el nombre
        if j['default_account_id']:
            # default_account_id viene como [123, "102.01.001 Banco Santander"]
            cuenta_texto = j['default_account_id'][1]
        
        print(f"{nombre:<35} | {cuenta_texto}")

except Exception as e:
    print(f"Error: {e}")