import xmlrpc.client
import ssl

# --- CONFIGURACIÓN Y CREDENCIALES ---
ODOO_URL = 'https://ebik.odoo.com'
ODOO_DB = 'ebik-prod-15375115'
ODOO_USER = 'sistemas@elitebike-mx.com'
ODOO_PASSWORD = 'bb36fdae62c3c113fb91de0143eba06da199672d'

# Fijamos el ID de la empresa a escanear (Elite Bike)
ODOO_COMPANY_ID = 1

def get_odoo_models():
    context = ssl._create_unverified_context()
    try:
        common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", context=context)
        models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", context=context)
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
        return uid, models
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return None, None

def escaner_de_cuentas():
    uid, models = get_odoo_models()
    if not uid: return

    fecha_fin = '2026-01-31'
    
    print(f"\n🔦 ESCANEANDO TODAS LAS CUENTAS MONEX (102.01.0X) AL {fecha_fin} (SOLO EMPRESA 1)")
    print("=" * 80)

    # 🚀 AQUÍ ESTÁ EL CAMBIO: Agregamos el filtro company_id
    domain = [
        ('company_id', '=', ODOO_COMPANY_ID), 
        ('date', '<=', fecha_fin), 
        ('parent_state', '=', 'posted'),
        ('account_id.code', '=like', '102.01.0%'),
    ]

    try:
        resultado = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'read_group',
            [domain],
            {'fields': ['balance'], 'groupby': ['account_id']}
        )

        for res in resultado:
            acc_info = res.get('account_id')
            if acc_info:
                nombre_cuenta = acc_info[1]
                balance = res.get('balance', 0.0)
                print(f"Cuenta Odoo: {nombre_cuenta:<50} | Balance: ${balance:>12,.2f}")

    except Exception as e:
        print(f"❌ Error: {e}")

    print("=" * 80 + "\n")

if __name__ == '__main__':
    escaner_de_cuentas()