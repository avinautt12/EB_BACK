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
    
    cuenta = '102.01.013'
    nomenclatura = 'PSAN52'
    frase_inversion = 'TRASPASO A BBVA PARA INVERSIÓN'
    
    domain = [
        ('date', '>=', '2026-02-01'),
        ('date', '<=', '2026-02-28'),
        ('parent_state', '=', 'posted'),
        ('account_id.code', '=', cuenta),
        '|', '|',
        ('name', 'ilike', nomenclatura),
        ('ref', 'ilike', nomenclatura),
        ('move_id.name', 'ilike', nomenclatura)
    ]

    try:
        # 🚨 CAMBIO 1: Agregamos 'move_id' a los fields
        apuntes = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read',
            [domain], 
            {'fields': ['date', 'name', 'ref', 'credit', 'move_id'], 'order': 'date ASC'}
        )

        total_haber = 0.0
        conteo = 0
        
        print(f"🔎 Buscando frase: '{frase_inversion}'")
        print("-" * 110)

        for a in apuntes:
            # 🚨 CAMBIO 2: Extraemos el nombre del asiento (Encabezado)
            asiento_nombre = a['move_id'][1] if a.get('move_id') else ""
            
            # Unimos todo para que el filtro no falle
            texto_busqueda = (str(a.get('name') or '') + " " + 
                             str(a.get('ref') or '') + " " + 
                             str(asiento_nombre)).upper()
            
            if frase_inversion.upper() in texto_busqueda:
                monto = float(a.get('credit', 0.0))
                total_haber += monto
                conteo += 1
                print(f"✅ {a.get('date')} | ${monto:>12,.2f} | Asiento: {asiento_nombre[:45]}")

        print("-" * 110)
        print(f"📈 Movimientos totales: {conteo}")
        print(f"💰 SUMA FINAL: ${total_haber:,.2f}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    test_inversiones_v3()