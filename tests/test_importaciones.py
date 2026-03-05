import xmlrpc.client
import ssl
import time

# --- CONFIGURACIÓN Y CREDENCIALES ---
ODOO_URL = 'https://ebik.odoo.com'
ODOO_DB = 'ebik-prod-15375115'
ODOO_USER = 'sistemas@elitebike-mx.com'
ODOO_PASSWORD = 'bb36fdae62c3c113fb91de0143eba06da199672d'

def get_odoo_models():
    print("🔄 Conectando a Odoo...")
    context = ssl._create_unverified_context()
    try:
        common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", context=context)
        models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", context=context)
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
        if uid:
            print("✅ Conexión exitosa a Odoo.\n")
            return uid, models
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
    return None, None

def test_importaciones():
    uid, models = get_odoo_models()
    if not uid:
        return

    # --- SIMULAMOS TU BASE DE DATOS (CON EL TYPO CORREGIDO Y LA PALABRA INCLUIDA) ---
    configuraciones = [
        {'cuenta': '102.01.10', 'nomenclatura': 'PBNK2/', 'regla': 'Solo_Debe', 'palabra_req': ''}, 
        {'cuenta': '102.01.01', 'nomenclatura': 'PBNK1/', 'regla': 'Solo_Debe', 'palabra_req': 'PEDIMENTO'}
    ]
    
    fecha_inicio = '2026-02-01'
    fecha_fin = '2026-02-28'

    print(f"🚢 EVALUANDO CONCEPTO: IMPORTACIONES Y ADUANAS")
    print("=" * 100)

    gran_total_concepto = 0.0

    for config in configuraciones:
        cuenta = config['cuenta']
        nomenclatura = config['nomenclatura']
        regla = config['regla']
        palabra_req = config['palabra_req']
        
        texto_filtro = f" | Exige: '{palabra_req}'" if palabra_req else ""
        print(f"\n🔎 BUSCANDO REGLA -> Cuenta: {cuenta} | Ref: {nomenclatura} | Regla: {regla}{texto_filtro}")
        
        # 🚀 LÓGICA INTELIGENTE DE CUENTAS (Búsqueda exacta para la 102.01.01)
        operador = '=' if len(cuenta) >= 8 else '=like'
        valor_busqueda = cuenta if operador == '=' else f"{cuenta}%"

        domain = [
            ('date', '>=', fecha_inicio),
            ('date', '<=', fecha_fin),
            ('parent_state', '=', 'posted'),
            ('account_id.code', operador, valor_busqueda),
            '|', '|', 
            ('name', 'ilike', nomenclatura), 
            ('ref', 'ilike', nomenclatura),
            ('move_id.name', 'ilike', nomenclatura)
        ]

        try:
            apuntes = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'account.move.line', 'search_read', 
                [domain], 
                {'fields': ['date', 'move_id', 'name', 'ref', 'debit', 'credit', 'partner_id', 'account_id'], 'order': 'date ASC'}
            )

            subtotal = 0.0
            print(f"{'FECHA':<12} | {'CUENTA REAL':<15} | {'ASIENTO / REF':<30} | {'DEBE (+)':>12} | {'HABER (-)':>12}")
            print("-" * 100)

            for a in apuntes:
                # 🛑 ESCUDO 1: Validar subcuentas de Odoo
                account_data = a.get('account_id')
                account_name = account_data[1] if account_data else ''
                codigo_real = account_name.split(' ')[0] if account_name else ''

                if operador == '=' and codigo_real != cuenta:
                    continue

                # 🛑 ESCUDO 2: Validar palabra incluida (PEDIMENTO)
                texto_linea = (str(a.get('name', '')) + ' ' + str(a.get('ref', ''))).upper()
                if palabra_req and palabra_req not in texto_linea:
                    continue # Lo ignoramos si no dice PEDIMENTO

                fecha = a.get('date', '')
                asiento = a['move_id'][1] if a.get('move_id') else str(a.get('name', ''))
                
                debe = float(a.get('debit', 0.0))
                haber = float(a.get('credit', 0.0))

                if regla == 'Solo_Debe':
                    subtotal += debe
                elif regla == 'Solo_Haber':
                    subtotal += haber

                print(f"{fecha:<12} | {codigo_real:<15} | {asiento[:30]:<30} | ${debe:>10,.2f} | ${haber:>10,.2f}")

            print("-" * 100)
            print(f"💰 SUBTOTAL DE ESTA REGLA ({nomenclatura}): ${subtotal:,.2f}")
            
            gran_total_concepto += subtotal

        except Exception as e:
            print(f"❌ Error al consultar Odoo: {e}")

    print("\n" + "=" * 100)
    print(f"🚀 GRAN TOTAL PARA EL CONCEPTO (Suma de ambas reglas): ${gran_total_concepto:,.2f}")
    print("=" * 100)

if __name__ == '__main__':
    test_importaciones()