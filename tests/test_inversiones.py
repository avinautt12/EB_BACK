import xmlrpc.client
import ssl

# --- CONFIGURACIÓN ---
ODOO_URL = 'https://ebik.odoo.com'
ODOO_DB = 'ebik-prod-15375115'
ODOO_USER = 'sistemas@elitebike-mx.com'
ODOO_PASSWORD = 'bb36fdae62c3c113fb91de0143eba06da199672d'

def get_odoo_models():
    context = ssl._create_unverified_context()
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", context=context)
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", context=context)
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
    return uid, models

def test_inversiones_v3():
    uid, models = get_odoo_models()
    
    cuenta = '103.01.01'
    
    domain = [
        ('date', '>=', '2026-01-01'),
        ('date', '<=', '2026-04-30'),
        ('parent_state', '=', 'posted'),
        ('account_id.code', '=', cuenta)
    ]

    try:
        # Obtenemos el campo 'balance'
        apuntes = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read',
            [domain], 
            {'fields': ['date', 'name', 'ref', 'balance', 'move_id'], 'order': 'date ASC'}
        )

        total_balance = 0.0
        conteo = 0
        
        print(f"🔎 Buscando movimientos de la cuenta {cuenta}")
        print("-" * 110)

        for a in apuntes:
            asiento_nombre = a['move_id'][1] if a.get('move_id') else ""
            monto = float(a.get('balance', 0.0))
            total_balance += monto
            conteo += 1
            print(f"✅ {a.get('date')} | ${monto:>12,.2f} | Asiento: {asiento_nombre[:45]}")

        print("-" * 110)
        print(f"📈 Movimientos totales: {conteo}")
        print(f"💰 BALANCE TOTAL: ${total_balance:,.2f}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    test_inversiones_v3()